# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import cint, cstr
from frappe import throw, _
from frappe.utils.nestedset import NestedSet, get_ancestors_of, get_descendants_of
from frappe.desk.reportview import get_match_cond, get_filters_cond

class RootNotEditable(frappe.ValidationError): pass
class BalanceMismatchError(frappe.ValidationError): pass

class Account(NestedSet):
	nsm_parent_field = 'parent_account'
	def on_update(self):
		if frappe.local.flags.ignore_on_update:
			return
		else:
			super(Account, self).on_update()

	def validate(self):
		if frappe.local.flags.allow_unverified_charts:
			return
		self.validate_parent()
		self.validate_root_details()
		self.validate_group_or_ledger()
		self.set_root_and_report_type()
		self.validate_mandatory()

	def validate_parent(self):
		"""Fetch Parent Details and validate parent account"""
		if self.parent_account:
			par = frappe.db.get_value("Account", self.parent_account,
				["name", "is_group", "company"], as_dict=1)
			if not par:
				throw(_("Account {0}: Parent account {1} does not exist").format(self.name, self.parent_account))
			elif par.name == self.name:
				throw(_("Account {0}: You can not assign itself as parent account").format(self.name))
			elif not par.is_group:
				throw(_("Account {0}: Parent account {1} can not be a ledger").format(self.name, self.parent_account))
			elif par.company != self.company:
				throw(_("Account {0}: Parent account {1} does not belong to company: {2}")
					.format(self.name, self.parent_account, self.company))

	def set_root_and_report_type(self):
		if self.parent_account:
			par = frappe.db.get_value("Account", self.parent_account,
				["report_type", "root_type"], as_dict=1)

			if par.report_type:
				self.report_type = par.report_type
			if par.root_type:
				self.root_type = par.root_type

		if self.is_group:
			db_value = frappe.db.get_value("Account", self.name, ["report_type", "root_type"], as_dict=1)
			if db_value:
				if self.report_type != db_value.report_type:
					frappe.db.sql("update `tabAccount` set report_type=%s where lft > %s and rgt < %s",
						(self.report_type, self.lft, self.rgt))
				if self.root_type != db_value.root_type:
					frappe.db.sql("update `tabAccount` set root_type=%s where lft > %s and rgt < %s",
						(self.root_type, self.lft, self.rgt))

		if self.root_type and not self.report_type:
			self.report_type = "Balance Sheet" \
				if self.root_type in ("Asset", "Liability", "Equity") else "Profit and Loss"

	def validate_root_details(self):
		# does not exists parent
		if frappe.db.exists("Account", self.name):
			if not frappe.db.get_value("Account", self.name, "parent_account"):
				throw(_("Root cannot be edited."), RootNotEditable)

		if not self.parent_account and not self.is_group:
			frappe.throw(_("Root Account must be a group"))

	def validate_group_or_ledger(self):
		if self.get("__islocal"):
			return

		existing_is_group = frappe.db.get_value("Account", self.name, "is_group")
		if cint(self.is_group) != cint(existing_is_group):
			if self.check_gle_exists():
				throw(_("Account with existing transaction cannot be converted to ledger"))
			elif self.is_group:
				if self.account_type and not self.flags.exclude_account_type_check:
					throw(_("Cannot covert to Group because Account Type is selected."))
			elif self.check_if_child_exists():
				throw(_("Account with child nodes cannot be set as ledger"))


	def convert_group_to_ledger(self):
		if self.check_if_child_exists():
			throw(_("Account with child nodes cannot be converted to ledger"))
		elif self.check_gle_exists():
			throw(_("Account with existing transaction cannot be converted to ledger"))
		else:
			self.is_group = 0
			self.save()
			return 1

	def convert_ledger_to_group(self):
		if self.check_gle_exists():
			throw(_("Account with existing transaction can not be converted to group."))
		elif self.account_type and not self.flags.exclude_account_type_check:
			throw(_("Cannot covert to Group because Account Type is selected."))
		else:
			self.is_group = 1
			self.save()
			return 1

	# Check if any previous balance exists
	def check_gle_exists(self):
		return frappe.db.get_value("GL Entry", {"account": self.name})

	def check_if_child_exists(self):
		return frappe.db.sql("""select name from `tabAccount` where parent_account = %s
			and docstatus != 2""", self.name)

	def validate_mandatory(self):
		if not self.root_type:
			throw(_("Root Type is mandatory"))

		if not self.report_type:
			throw(_("Report Type is mandatory"))

	def on_trash(self):
		# checks gl entries and if child exists
		if self.check_gle_exists():
			throw(_("Account with existing transaction can not be deleted"))

		super(Account, self).on_trash(True)

def get_parent_account(doctype, txt, searchfield, start, page_len, filters):
	return frappe.db.sql("""select name from tabAccount
		where is_group = 1 and docstatus != 2 and company = %s
		and %s like %s order by name limit %s, %s""" %
		("%s", searchfield, "%s", "%s", "%s"),
		(filters["company"], "%%%s%%" % txt, start, page_len), as_list=1)

def on_doctype_update():
	frappe.db.add_index("Account", ["lft", "rgt"])

def get_account_autoname(account_number, account_name, company):
	# first validate if company exists
	company = frappe.get_cached_value('Company',  company,  ["abbr", "name"], as_dict=True)
	if not company:
		frappe.throw(_('Company {0} does not exist').format(company))

	parts = [account_name.strip(), company.abbr]
	if cstr(account_number).strip():
		parts.insert(0, cstr(account_number).strip())
	return ' - '.join(parts)

def validate_account_number(name, account_number, company):
	if account_number:
		account_with_same_number = frappe.db.get_value("Account",
			{"account_number": account_number, "company": company, "name": ["!=", name]})
		if account_with_same_number:
			frappe.throw(_("Account Number {0} already used in account {1}")
				.format(account_number, account_with_same_number))

@frappe.whitelist()
def update_account_number(name, account_name, account_number=None):

	account = frappe.db.get_value("Account", name, "company", as_dict=True)
	if not account: return
	validate_account_number(name, account_number, account.company)
	if account_number:
		frappe.db.set_value("Account", name, "account_number", account_number.strip())
	else:
		frappe.db.set_value("Account", name, "account_number", "")
	frappe.db.set_value("Account", name, "account_name", account_name.strip())

	new_name = get_account_autoname(account_number, account_name, account.company)
	if name != new_name:
		frappe.rename_doc("Account", name, new_name, force=1)
		return new_name

@frappe.whitelist()
def merge_account(old, new, is_group, root_type, company):
	# Validate properties before merging
	if not frappe.db.exists("Account", new):
		throw(_("Account {0} does not exist").format(new))

	val = list(frappe.db.get_value("Account", new,
		["is_group", "root_type", "company"]))

	if val != [cint(is_group), root_type, company]:
		throw(_("""Merging is only possible if following properties are same in both records. Is Group, Root Type, Company"""))

	if is_group and frappe.db.get_value("Account", new, "parent_account") == old:
		frappe.db.set_value("Account", new, "parent_account",
			frappe.db.get_value("Account", old, "parent_account"))

	frappe.rename_doc("Account", old, new, merge=1, force=1)

	return new

@frappe.whitelist()
def get_root_company(company):
	# return the topmost company in the hierarchy
	ancestors = get_ancestors_of('Company', company, "lft asc")
	return [ancestors[0]] if ancestors else []

@frappe.whitelist()
def get_expense_account(doctype, txt, searchfield, start, page_len, filters):
	
	if not filters: filters = {}

	condition = ""
	if filters.get("company"):
		condition += "and tabAccount.company = %(company)s"

	return frappe.db.sql("""select tabAccount.name from `tabAccount`
		where (tabAccount.report_type = "Profit and Loss"
				or tabAccount.account_type in ("Expense Account", "Fixed Asset", "Temporary", "Asset Received But Not Billed", "Capital Work in Progress"))
			and tabAccount.is_group=0
			and tabAccount.docstatus!=2
			and tabAccount.{key} LIKE %(txt)s
			{condition} {match_condition}"""
		.format(condition=condition, key=searchfield,
			match_condition=get_match_cond(doctype)), {
			'company': filters.get("company", ""),
			'txt': '%' + txt + '%'
		})