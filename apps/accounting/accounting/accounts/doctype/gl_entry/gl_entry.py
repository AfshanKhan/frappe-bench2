# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, accounting
from frappe import _
from frappe.utils import flt, fmt_money, getdate, formatdate
from frappe.model.document import Document
from frappe.model.naming import set_name_from_naming_options
from frappe.model.meta import get_field_precision

class GLEntry(Document):
	def autoname(self):
		"""
		Temporarily name doc for fast insertion
		name will be changed using autoname options (in a scheduled job)
		"""
		self.name = frappe.generate_hash(txt="", length=10)

	def validate(self):
		self.flags.ignore_submit_comment = True
		self.check_mandatory()
		
		if not self.flags.from_repost:
			self.check_pl_account()

	def on_update_with_args(self, adv_adj, update_outstanding = 'Yes', from_repost=False):
		if not from_repost:
			self.validate_account_details(adv_adj)
			
		validate_balance_type(self.account, adv_adj)

		# Update outstanding amt on against voucher
		if self.against_voucher_type in ['Journal Entry', 'Sales Invoice', 'Purchase Invoice'] \
			and self.against_voucher and update_outstanding == 'Yes' and not from_repost:
				update_outstanding_amt(self.account, self.party_type, self.party, self.against_voucher_type,
					self.against_voucher)

	def check_mandatory(self):
		mandatory = ['account','voucher_type','voucher_no','company']
		for k in mandatory:
			if not self.get(k):
				frappe.throw(_("{0} is required").format(_(self.meta.get_label(k))))

		account_type = frappe.db.get_value("Account", self.account, "account_type")
		if not (self.party_type and self.party):
			if account_type == "Receivable":
				frappe.throw(_("{0} {1}: Customer is required against Receivable account {2}")
					.format(self.voucher_type, self.voucher_no, self.account))
			elif account_type == "Payable":
				frappe.throw(_("{0} {1}: Supplier is required against Payable account {2}")
					.format(self.voucher_type, self.voucher_no, self.account))

		# Zero value transaction is not allowed
		if not (flt(self.debit, self.precision("debit")) or flt(self.credit, self.precision("credit"))):
			frappe.throw(_("{0} {1}: Either debit or credit amount is required for {2}")
				.format(self.voucher_type, self.voucher_no, self.account))

	def check_pl_account(self):
		if self.is_opening=='Yes' and \
				frappe.db.get_value("Account", self.account, "report_type")=="Profit and Loss" and \
				self.voucher_type not in ['Purchase Invoice', 'Sales Invoice']:
			frappe.throw(_("{0} {1}: 'Profit and Loss' type account {2} not allowed in Opening Entry")
				.format(self.voucher_type, self.voucher_no, self.account))

	def validate_account_details(self, adv_adj):
		"""Account must be ledger, active and not freezed"""

		ret = frappe.db.sql("""select is_group, docstatus, company
			from tabAccount where name=%s""", self.account, as_dict=1)[0]

		if ret.is_group==1:
			frappe.throw(_("{0} {1}: Account {2} cannot be a Group")
				.format(self.voucher_type, self.voucher_no, self.account))

		if ret.docstatus==2:
			frappe.throw(_("{0} {1}: Account {2} is inactive")
				.format(self.voucher_type, self.voucher_no, self.account))

		if ret.company != self.company:
			frappe.throw(_("{0} {1}: Account {2} does not belong to Company {3}")
				.format(self.voucher_type, self.voucher_no, self.account, self.company))

def validate_balance_type(account, adv_adj=False):
	if not adv_adj and account:
		balance_must_be = frappe.db.get_value("Account", account, "balance_must_be")
		if balance_must_be:
			balance = frappe.db.sql("""select sum(debit) - sum(credit)
				from `tabGL Entry` where account = %s""", account)[0][0]

			if (balance_must_be=="Debit" and flt(balance) < 0) or \
				(balance_must_be=="Credit" and flt(balance) > 0):
				frappe.throw(_("Balance for Account {0} must always be {1}").format(account, _(balance_must_be)))

def update_outstanding_amt(account, party_type, party, against_voucher_type, against_voucher, on_cancel=False):
	if party_type and party:
		party_condition = " and party_type={0} and party={1}"\
			.format(frappe.db.escape(party_type), frappe.db.escape(party))
	else:
		party_condition = ""

	if against_voucher_type == "Sales Invoice":
		party_account = frappe.db.get_value(against_voucher_type, against_voucher, "debit_to")
		account_condition = "and account in ({0}, {1})".format(frappe.db.escape(account), frappe.db.escape(party_account))
	else:
		account_condition = " and account = {0}".format(frappe.db.escape(account))

	# get final outstanding amt
	bal = flt(frappe.db.sql("""
		select sum(debit) - sum(credit)
		from `tabGL Entry`
		where against_voucher_type=%s and against_voucher=%s
		and voucher_type != 'Invoice Discounting'
		{0} {1}""".format(party_condition, account_condition),
		(against_voucher_type, against_voucher))[0][0] or 0.0)

	if against_voucher_type == 'Purchase Invoice':
		bal = -bal
	elif against_voucher_type == "Journal Entry":
		against_voucher_amount = flt(frappe.db.sql("""
			select sum(debit) - sum(credit)
			from `tabGL Entry` where voucher_type = 'Journal Entry' and voucher_no = %s
			and account = %s and (against_voucher is null or against_voucher='') {0}"""
			.format(party_condition), (against_voucher, account))[0][0])

		if not against_voucher_amount:
			frappe.throw(_("Against Journal Entry {0} is already adjusted against some other voucher")
				.format(against_voucher))

		bal = against_voucher_amount + bal
		if against_voucher_amount < 0:
			bal = -bal

		# Validation : Outstanding can not be negative for JV
		if bal < 0 and not on_cancel:
			frappe.throw(_("Outstanding for {0} cannot be less than zero ({1})").format(against_voucher, fmt_money(bal)))

def on_doctype_update():
	frappe.db.add_index("GL Entry", ["against_voucher_type", "against_voucher"])
	frappe.db.add_index("GL Entry", ["voucher_type", "voucher_no"])

def rename_gle_sle_docs():
	for doctype in ["GL Entry"]:
		rename_temporarily_named_docs(doctype)

def rename_temporarily_named_docs(doctype):
	"""Rename temporarily named docs using autoname options"""
	docs_to_rename = frappe.get_all(doctype, {"to_rename": "1"}, order_by="creation", limit=50000)
	for doc in docs_to_rename:
		oldname = doc.name
		set_name_from_naming_options(frappe.get_meta(doctype).autoname, doc)
		newname = doc.name
		frappe.db.sql("""UPDATE `tab{}` SET name = %s, to_rename = 0 where name = %s""".format(doctype), (newname, oldname))
