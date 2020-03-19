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
from accounting.stock import get_warehouse_account_map
from accounting.accounts.general_ledger import make_gl_entries, merge_similar_entries
from frappe.model.mapper import get_mapped_doc
from six import iteritems


cash_account = frappe.db.get_value("Account", "Cash", as_dict=True)
# # print(cash_account)
stock_account = frappe.db.get_value("Account", "Stock In Hand", as_dict=True)
# # print(stock_account)
sales_account = frappe.db.get_value("Account", "Sales", as_dict=True)
# # print(sales_account)
cogs_account = frappe.db.get_value("Account", "Cost of Goods Sold", as_dict=True)
# # print(cogd_account)
# company = frappe.db.get_value("Company", "Gada Electronics", as_dict=True)
# # print(company)

class PurchaseInvoice(Document):
	
	def validate(self):
		
		self.cash_account = cash_account
		self.stock_account = stock_account
		self.sales_account = sales_account
		self.cogs_account = cogs_account
		# self.company = company
		# self.doctype = "Purchase Invoice"
		# print(self.company)

		
		if not self.is_opening:
			self.is_opening = 'No'

		self.set_status()

		
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
		self.validate()
		self.make_gl_entries()

	def make_gl_entries(self, gl_entries=None, repost_future_gle=True, from_repost=False):
		if not self.total:
			return
		if not gl_entries:
			gl_entries = self.get_gl_entries()

		if gl_entries:
			make_gl_entries(gl_entries,  cancel=(self.docstatus == 2), merge_entries=False, from_repost=from_repost)

			# update _outstanding_amt(self.credit_to, "Supplier", self.supplier, self.doctype, self.name)

	def get_gl_entries(self, warehouse_account=None):
		gl_entries = []

		self.make_stock_gl_entry(gl_entries)

		gl_entries = merge_similar_entries(gl_entries)

		return gl_entries

	def make_stock_gl_entry(self, gl_entries):
		cred = get_gl_dict({
				"account": self.cash_account,
				"party_type": "Supplier",
				"party": self.supplier,
				"against": self.supplier,
				"credit": self.total,
				"against_voucher": self.name,
				"against_voucher_type": self.doctype,
			})
		gl_entries.append(cred)

		debt = get_gl_dict({
				"account": self.stock_account,
				"party_type": "Supplier",
				"party": self.supplier,
				"against": self.cash_account,
				"debit": self.total,
				"against_voucher": self.name,
				"against_voucher_type": self.doctype,
			})

		gl_entries.append(debt)

		

		# gl_entries.append(
		# 	get_gl_dict({
		# 		"account": self.sales_account,
		# 		"against": self.cogd_account,
		# 		"debit": self.total,
		# 	})
		# )

		# gl_entries.append(
		# 	get_gl_dict({
		# 		"account": self.cogd_account,
		# 		"against": self.stock_account,
		# 		"credit": self.total,
		# 	})
		# )

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
