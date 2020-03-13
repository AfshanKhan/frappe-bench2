# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
# import frappe
# from frappe.model.document import Document

import frappe, os, json
from frappe import _
from frappe.utils import get_timestamp

# from frappe.utils import cint, today, formatdate
# import frappe.defaults
from frappe.cache_manager import clear_defaults_cache

from frappe.model.document import Document
# from frappe.contacts.address_and_contact import load_address_and_contact
# from frappe.utils.nestedset import NestedSet

from past.builtins import cmp
# import functools
from frappe.utils.nestedset import rebuild_tree
from six import iteritems
from frappe.utils import cstr
from unidecode import unidecode


class Company(Document):
	# pass

# class Company(NestedSet):

	# def onload(self):
	# 	self.get("__onload")["transactions_exist"] = self.check_if_transactions_exist()

	def check_if_transactions_exist(self):
		exists = False
		for doctype in ["Sales Invoice", "Delivery Note", "Sales Order", "Quotation",
			"Purchase Invoice", "Purchase Receipt", "Purchase Order", "Supplier Quotation"]:
				if frappe.db.sql("""select name from `tab%s` where company=%s and docstatus=1
					limit 1""" % (doctype, "%s"), self.name):
						exists = True
						break

		return exists

	def validate(self):
		self.validate_abbr()
		
	def validate_abbr(self):
		if not self.abbr:
			self.abbr = ''.join([c[0] for c in self.company_name.split()]).upper()

		self.abbr = self.abbr.strip()

		# if self.get('__islocal') and len(self.abbr) > 5:
		# 	frappe.throw(_("Abbreviation cannot have more than 5 characters"))

		if not self.abbr.strip():
			frappe.throw(_("Abbreviation is mandatory"))

		if frappe.db.sql("select abbr from tabCompany where name!=%s and abbr=%s", (self.name, self.abbr)):
			frappe.throw(_("Abbreviation already used for another company"))

	def on_update(self):
	# 	NestedSet.on_update(self)
		if not frappe.db.sql("""select name from tabAccount
				where company=%s and docstatus<2 limit 1""", self.name):
			# if not frappe.local.flags.ignore_chart_of_accounts:
			self.create_charts_of_accounts()
			# self.create_default_warehouses()
		
		frappe.clear_cache()

	def create_default_warehouses(self):
		for wh_detail in [
			{"warehouse_name": _("All Warehouses"), "is_group": 1},
			{"warehouse_name": _("Stores"), "is_group": 0},
			{"warehouse_name": _("Work In Progress"), "is_group": 0},
			{"warehouse_name": _("Finished Goods"), "is_group": 0}]:

			if not frappe.db.exists("Warehouse", "{0} - {1}".format(wh_detail["warehouse_name"], self.abbr)):
				warehouse = frappe.get_doc({
					"doctype":"Warehouse",
					"warehouse_name": wh_detail["warehouse_name"],
					"is_group": wh_detail["is_group"],
					"company": self.name,
					"parent_warehouse": "" if wh_detail["is_group"] else "{0} - {1}".format(_("All Warehouses"), self.abbr)
				})
				warehouse.flags.ignore_permissions = True
				warehouse.flags.ignore_mandatory = True
				warehouse.insert()	

	def create_charts_of_accounts(self):
		chart = get_chart()
		if chart:
			accounts = []

			def _import_accounts(children, parent, root_type, root_account=False):
				for account_name, child in iteritems(children):
					if root_account:
						root_type = child.get("root_type")

					if account_name not in ["account_number", "account_type",
						"root_type", "is_group"]:

						account_number = cstr(child.get("account_number")).strip()
						account_name, account_name_in_db = add_suffix_if_duplicate(account_name,
							account_number, accounts)

						is_group = identify_is_group(child)
						report_type = "Balance Sheet" if root_type in ["Asset", "Liability"] \
							else "Profit and Loss"

						account = frappe.get_doc({
							"doctype": "Account",
							"account_name": account_name,
							"company": self.name,
							"parent_account": parent,
							"is_group": is_group,
							"root_type": root_type,
							"report_type": report_type,
							"account_number": account_number,
							"account_type": child.get("account_type")
						})

						if root_account or frappe.local.flags.allow_unverified_charts:
							account.flags.ignore_mandatory = True

						account.flags.ignore_permissions = True

						account.insert()

						accounts.append(account_name_in_db)

						_import_accounts(child, account.name, root_type)

			# Rebuild NestedSet HSM tree for Account Doctype
			# after all accounts are already inserted.
			frappe.local.flags.ignore_on_update = True
			_import_accounts(chart, None, None, root_account=True)
			rebuild_tree("Account", "parent_account")
			frappe.local.flags.ignore_on_update = False

	
	def after_rename(self, olddn, newdn, merge=False):
		frappe.db.set(self, "company_name", newdn)

		clear_defaults_cache()

	def abbreviate(self):
		self.abbr = ''.join([c[0].upper() for c in self.company_name.split()])

	# def on_trash(self):
	# 	"""
	# 		Trash accounts and cost centers for this company if no gl entry exists
	# 	"""
	# 	frappe.utils.nestedset.update_nsm(self)

	# 	rec = frappe.db.sql("SELECT name from `tabGL Entry` where company = %s", self.name)
	# 	if not rec:
	# 		frappe.db.sql("""delete from `tabBudget Account`
	# 			where exists(select name from tabBudget
	# 				where name=`tabBudget Account`.parent and company = %s)""", self.name)

	# 		for doctype in ["Account", "Cost Center", "Budget", "Party Account"]:
	# 			frappe.db.sql("delete from `tab{0}` where company = %s".format(doctype), self.name)

	# 	if not frappe.db.get_value("Stock Ledger Entry", {"company": self.name}):
	# 		frappe.db.sql("""delete from `tabWarehouse` where company=%s""", self.name)

	# 	# clear default accounts, warehouses from item
	# 	warehouses = frappe.db.sql_list("select name from tabWarehouse where company=%s", self.name)
	# 	if warehouses:
	# 		frappe.db.sql("""delete from `tabItem Reorder` where warehouse in (%s)"""
	# 			% ', '.join(['%s']*len(warehouses)), tuple(warehouses))

	
	# 	frappe.db.sql("delete from tabEmployee where company=%s", self.name)
	# 	frappe.db.sql("delete from tabDepartment where company=%s", self.name)
	


def get_chart():
		return {
			_("Application of Funds (Assets)"): {
				_("Current Assets"): {
					_("Accounts Receivable"): {
						_("Debtors"): {
							"account_type": "Receivable"
						}
					},
					_("Cash In Hand"): {
						_("Cash"): {
							"account_type": "Cash"
						},
						"account_type": "Cash"
					},
					_("Stock Assets"): {
						_("Stock In Hand"): {
							"account_type": "Stock"
						},
						"account_type": "Stock",
					},
				},
				_("Temporary Accounts"): {
					_("Temporary Opening"): {
						"account_type": "Temporary"
					}
				},
				"root_type": "Asset"
			},
			_("Expenses"): {
				_("Direct Expenses"): {
					_("Stock Expenses"): {
						_("Cost of Goods Sold"): {
							"account_type": "Cost of Goods Sold"
						},
						_("Expenses Included In Asset Valuation"): {
							"account_type": "Expenses Included In Asset Valuation"
						},
						_("Expenses Included In Valuation"): {
							"account_type": "Expenses Included In Valuation"
						},
						_("Stock Adjustment"): {
							"account_type": "Stock Adjustment"
						}
					},
				},
				_("Indirect Expenses"): {
					_("Miscellaneous Expenses"): {
						"account_type": "Chargeable"
					},
					_("Sales Expenses"): {},
					},
				"root_type": "Expense"
			},
			_("Income"): {
				_("Direct Income"): {
					_("Sales"): {},
					_("Service"): {}
				},
				_("Indirect Income"): {
					"is_group": 1
				},
				"root_type": "Income"
			},
			_("Source of Funds (Liabilities)"): {
				_("Current Liabilities"): {
					_("Accounts Payable"): {
						_("Creditors"): {
							"account_type": "Payable"
						},
					},
				},
				_("Capital Account"): {
					_("Shareholders Funds"): {},
				},
					_("Stock Liabilities"): {
						_("Stock Received But Not Billed"): {
							"account_type": "Stock Received But Not Billed"
						},
					},
				
				"root_type": "Liability"
				},
		}

def add_suffix_if_duplicate(account_name, account_number, accounts):
		if account_number:
			account_name_in_db = unidecode(" - ".join([account_number,
				account_name.strip().lower()]))
		else:
			account_name_in_db = unidecode(account_name.strip().lower())

		if account_name_in_db in accounts:
			count = accounts.count(account_name_in_db)
			account_name = account_name + " " + cstr(count)

		return account_name, account_name_in_db
	
def identify_is_group(child):
		if child.get("is_group"):
			is_group = child.get("is_group")
		elif len(set(child.keys()) - set(["account_type", "root_type", "is_group", "account_number"])):
			is_group = 1
		else:
			is_group = 0

		return is_group

@frappe.whitelist()
def enqueue_replace_abbr(company, old, new):
	kwargs = dict(company=company, old=old, new=new)
	frappe.enqueue('accounting.setup.doctype.company.company.replace_abbr', **kwargs)


@frappe.whitelist()
def replace_abbr(company, old, new):
	new = new.strip()
	if not new:
		frappe.throw(_("Abbr can not be blank or space"))

	frappe.only_for("System Manager")

	frappe.db.set_value("Company", company, "abbr", new)

	def _rename_record(doc):
		parts = doc[0].rsplit(" - ", 1)
		if len(parts) == 1 or parts[1].lower() == old.lower():
			frappe.rename_doc(dt, doc[0], parts[0] + " - " + new, force=True)

	def _rename_records(dt):
		# rename is expensive so let's be economical with memory usage
		doc = (d for d in frappe.db.sql("select name from `tab%s` where company=%s" % (dt, '%s'), company))
		for d in doc:
			_rename_record(d)

	# for dt in ["Warehouse", "Account", "Cost Center", "Department",
	# 		"Sales Taxes and Charges Template", "Purchase Taxes and Charges Template"]:
	# 	_rename_records(dt)
	# 	frappe.db.commit()


def get_name_with_abbr(name, company):
	company_abbr = frappe.get_cached_value('Company',  company,  "abbr")
	parts = name.split(" - ")

	if parts[-1].lower() != company_abbr.lower():
		parts.append(company_abbr)

	return " - ".join(parts)


# def get_all_transactions_annual_history(company):
# 	out = {}

# 	items = frappe.db.sql('''
# 		select transaction_date, count(*) as count

# 		from (
# 			select name, transaction_date, company
# 			from `tabQuotation`

# 			UNION ALL

# 			select name, transaction_date, company
# 			from `tabSales Order`

# 			UNION ALL

# 			select name, posting_date as transaction_date, company
# 			from `tabDelivery Note`

# 			UNION ALL

# 			select name, posting_date as transaction_date, company
# 			from `tabSales Invoice`

# 			UNION ALL

# 			select name, creation as transaction_date, company
# 			from `tabIssue`

# 			UNION ALL

# 			select name, creation as transaction_date, company
# 			from `tabProject`
# 		) t

# 		where
# 			company=%s
# 			and
# 			transaction_date > date_sub(curdate(), interval 1 year)

# 		group by
# 			transaction_date
# 			''', (company), as_dict=True)

# 	for d in items:
# 		timestamp = get_timestamp(d["transaction_date"])
# 		out.update({ timestamp: d["count"] })

# 	return out

# def get_timeline_data(doctype, name):
# 	'''returns timeline data based on linked records in dashboard'''
# 	out = {}
# 	date_to_value_dict = {}

# 	history = frappe.get_cached_value('Company',  name,  "transactions_annual_history")

# 	try:
# 		date_to_value_dict = json.loads(history) if history and '{' in history else None
# 	except ValueError:
# 		date_to_value_dict = None

# 	if date_to_value_dict is None:
# 		update_transactions_annual_history(name, True)
# 		history = frappe.get_cached_value('Company',  name,  "transactions_annual_history")
# 		return json.loads(history) if history and '{' in history else {}

# 	return date_to_value_dict