# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, accounting
import frappe.defaults
from frappe.model.document import Document
from frappe.utils import cint, flt, add_months, today, date_diff, getdate, add_days, cstr, nowdate
from frappe import _, msgprint, throw
from accounting.accounts.doctype.journal_entry.journal_entry import get_party_account, get_gl_dict
from accounting.accounts.doctype.purchase_invoice.purchase_invoice import get_stock_items
from accounting.accounts.general_ledger import make_gl_entries, merge_similar_entries
from accounting.accounts.doctype.gl_entry.gl_entry import update_outstanding_amt
from frappe.model.mapper import get_mapped_doc
from six import iteritems

ia = frappe.db.get_value("Account", "Sales", as_dict=False)

class SalesInvoice(Document):

	def validate(self):
		self.validate_debit_to_acc()
		if not self.is_opening_entry:
			self.is_opening_entry = 'No'
		self.set_income_account(for_validate=True)
		self.set_against_income_account()
		self.set_status()
		
	def on_submit(self):
		self.make_gl_entries()
	
	def validate_debit_to_acc(self):
		account = frappe.get_cached_value("Account", self.debit_to,
			["account_type", "report_type"], as_dict=True)

		if not account:
			frappe.throw(_("Debit To is required"))

		if account.report_type != "Balance Sheet":
			frappe.throw(_("Debit To account must be a Balance Sheet account"))

		if self.customer and account.account_type != "Receivable":
			frappe.throw(_("Debit To account must be a Receivable account"))

	def set_income_account(self, for_validate=False):
		income_account = ia
		stock_items = get_stock_items(self)

		if self.update_stock:
			self.validate_item_code()

		for item in self.get("items"):
			if item.item_code in stock_items and self.is_opening_entry == 'No':
				item.income_account = income_account

			elif not item.income_account and for_validate:
				throw(_("Income account is mandatory for item {0}").format(item.item_code or item.item_name))


	def set_against_income_account(self):
		"""Set against account for debit to account"""
		against_acc = []
		for d in self.get('items'):
			if d.income_account and d.income_account not in against_acc:
				against_acc.append(d.income_account)
		self.against_income_account = ','.join(against_acc)

	def validate_item_code(self):
		for d in self.get('items'):
			if not d.item_code:
				msgprint(_("Item Code required at Row No {0}").format(d.idx), raise_exception=True)

	def make_gl_entries(self, gl_entries=None, repost_future_gle=True, from_repost=False):
		if not gl_entries:
			gl_entries = self.get_gl_entries()

		if gl_entries:
			# # if POS and amount is written off, updating outstanding amt after posting all gl entries
			# update_outstanding = "No" if (cint(self.is_pos) or self.write_off_account or
			# 	cint(self.redeem_loyalty_points)) else "Yes"

			make_gl_entries(gl_entries, cancel=(self.docstatus == 2), merge_entries=False, from_repost=from_repost)

			update_outstanding_amt(self.debit_to, "Customer", self.customer,
				self.doctype, self.name)

	def get_gl_entries(self, warehouse_account=None):
		gl_entries = []

		self.make_customer_gl_entry(gl_entries)

		self.make_item_gl_entries(gl_entries)

		# merge gl entries before adding pos entries
		gl_entries = merge_similar_entries(gl_entries)

		return gl_entries

	def make_customer_gl_entry(self, gl_entries):
		gl_entries.append(
			get_gl_dict(self, args={
				"account": self.debit_to,
				"party_type": "Customer",
				"party": self.customer,
				"against": self.against_income_account,
				"debit": self.total,
				"against_voucher": self.name,
				"against_voucher_type": self.doctype,
			})
		)

	def make_item_gl_entries(self, gl_entries):
		# income account gl entries
		for item in self.get("items"):
			if flt(item.amount, item.precision("amount")):
				gl_entries.append(
					get_gl_dict(self, args={
						"account": item.income_account,
						"against": self.customer,
						"credit": flt(item.amount, item.precision("amount")),
					}, item=item)
				)
	
	def set_status(self, update=False, status=None, update_modified=True):
		if self.is_new():
			if self.get('amended_from'):
				self.status = 'Draft'
			return

		if not status:
			args = [
				self.docstatus,
			]
			status = get_status(args)

		if update:
			self.db_set('status', status, update_modified = update_modified)

def get_status(*args):
	docstatus = args[0]
	
	if docstatus == 2:
		status = "Cancelled"
	elif docstatus == 1:
		status = "Submitted"
	else:
		status = "Draft"
	
	return status