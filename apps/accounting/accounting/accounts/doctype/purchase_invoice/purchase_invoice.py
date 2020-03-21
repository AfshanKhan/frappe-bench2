# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, accounting
from frappe.utils import cint, cstr, formatdate, flt, getdate, nowdate
from frappe import _, throw
import frappe.defaults
from frappe.model.document import Document
from accounting.accounts.doctype.journal_entry.journal_entry import get_party_account, get_fiscal_year, get_gl_dict
from accounting.accounts.doctype.gl_entry.gl_entry import update_outstanding_amt
from accounting.accounts.general_ledger import make_gl_entries, merge_similar_entries
from frappe.model.mapper import get_mapped_doc
from six import iteritems

srnb = frappe.db.get_value("Account", "Stock Received But Not Billed", as_dict=False)

class PurchaseInvoice(Document):
	
	def validate(self):
		if not self.is_opening:
			self.is_opening = 'No'

		self.validate_credit_to_acc()
		self.set_expense_account(for_validate=True)
		self.set_against_expense_account()
		self.set_status()

	def validate_credit_to_acc(self):
		account = frappe.db.get_value("Account", self.credit_to,
			["account_type", "report_type"], as_dict=True)

		if account.report_type != "Balance Sheet":
			frappe.throw(_("Credit To account must be a Balance Sheet account"))

		if self.supplier and account.account_type != "Payable":
			frappe.throw(_("Credit To account must be a Payable account"))

	def set_expense_account(self, for_validate=False):
		stock_not_billed_account = srnb
		stock_items = self.get_stock_items()

		if self.update_stock:
			self.validate_item_code()

		for item in self.get("items"):
			if item.item_code in stock_items and self.is_opening == 'No':
				item.expense_account = stock_not_billed_account

			elif not item.expense_account and for_validate:
				throw(_("Expense account is mandatory for item {0}").format(item.item_code or item.item_name))

	def validate_item_code(self):
		for d in self.get('items'):
			if not d.item_code:
				frappe.msgprint(_("Item Code required at Row No {0}").format(d.idx), raise_exception=True)

	def set_against_expense_account(self):
		against_accounts = []
		for item in self.get("items"):
			if item.expense_account and (item.expense_account not in against_accounts):
				against_accounts.append(item.expense_account)

		self.against_expense_account = ",".join(against_accounts)

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

	def on_submit(self):
		self.make_gl_entries()

	def make_gl_entries(self, gl_entries=None, repost_future_gle=True, from_repost=False):
		if not self.total:
			return
		if not gl_entries:
			gl_entries = self.get_gl_entries()

		if gl_entries:
			make_gl_entries(gl_entries,  cancel=(self.docstatus == 2), merge_entries=False, from_repost=from_repost)

			update_outstanding_amt(self.credit_to, "Supplier", self.supplier, self.doctype, self.name)

	def get_gl_entries(self, warehouse_account=None):
		gl_entries = []
		self.make_supplier_gl_entry(gl_entries)
		self.make_item_gl_entries(gl_entries)

		gl_entries = merge_similar_entries(gl_entries)

		return gl_entries

	def make_supplier_gl_entry(self, gl_entries):
		print(self.posting_date)
		gl_entries.append(
			get_gl_dict(self, args={
				"account": self.credit_to,
				"party_type": "Supplier",
				"party": self.supplier,
				"against": self.against_expense_account,
				"credit": self.total,
				"against_voucher": self.name,
				"against_voucher_type": self.doctype,
			})
		)
		print(gl_entries)
	
	def make_item_gl_entries(self, gl_entries):
		# item gl entries
		stock_items = self.get_stock_items()
		for item in self.get("items"):
			if flt(item.amount):
				amount = flt(item.amount, item.precision("amount"))
				gl_entries.append(get_gl_dict(self, args={
						"account": item.expense_account,
						"against": self.supplier,
						"debit": amount,
					}, item=item))

	def get_stock_items(self):
			stock_items = []
			item_codes = list(set(item.item_code for item in self.get("items")))
			if item_codes:
				stock_items = [r[0] for r in frappe.db.sql("""
					select name from `tabItem`
					where name in (%s) and is_stock_item=1
				""" % (", ".join((["%s"] * len(item_codes))),), item_codes)]

			return stock_items

def get_status(*args):
	docstatus = args[0]
	if docstatus == 2:
		status = "Cancelled"
	elif docstatus == 1:
		status = "Submitted"
	else:
		status = "Draft"
	
	return status
