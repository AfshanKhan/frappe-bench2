# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class Item(Document):
	# pass
	def before_insert(self):
		if not self.description:
			self.description = self.item_name

	def validate(self):
		if not self.item_name:
			self.item_name = self.item_code

		if not self.description:
			self.description = self.item_name

		self.cant_change()

	def cant_change(self):
		if not self.get("__islocal"):
			fields = ("is_stock_item", "valuation_method")

			values = frappe.db.get_value("Item", self.name, fields, as_dict=True)
			if not values.get('valuation_method') and self.get('valuation_method'):
				values['valuation_method'] =  "FIFO"

			if values:
				for field in fields:
					if cstr(self.get(field)) != cstr(values.get(field)):
						if not self.check_if_linked_document_exists(field):
							break # no linked document, allowed
						else:
							frappe.throw(_("As there are existing transactions against item {0}, you can not change the value of {1}").format(self.name, frappe.bold(self.meta.get_label(field))))

	def before_rename(self, old_name, new_name, merge=False):
		if self.item_name == old_name:
			frappe.db.set_value("Item", old_name, "item_name", new_name)

		if merge:
		# Validate properties before merging
			if not frappe.db.exists("Item", new_name):
				frappe.throw(_("Item {0} does not exist").format(new_name))

			field_list = ["is_stock_item"]
			new_properties = [cstr(d) for d in frappe.db.get_value("Item", new_name, field_list)]
			if new_properties != [cstr(self.get(fld)) for fld in field_list]:
				frappe.throw(_("To merge, following properties must be same for both items")
									+ ": \n" + ", ".join([self.meta.get_label(fld) for fld in field_list]))

	def after_rename(self, old_name, new_name, merge):
		if self.route:
			clear_cache(self.route)

		frappe.db.set_value("Item", new_name, "item_code", new_name)

	def check_if_linked_document_exists(self, field):
		linked_doctypes = ["Sales Invoice Item", "Purchase Invoice Item"]

		for doctype in linked_doctypes:
			if frappe.db.get_value(doctype, filters={"item_code": self.name, "docstatus": 1}) or \
				frappe.db.get_value("Production Order",
					filters={"production_item": self.name, "docstatus": 1}):
				return True

	def create_onboarding_docs(self, args):
		for i in range(1, args.get('max_count')):
			item = args.get('item_' + str(i))
			if item:
				default_warehouse = ''
				default_warehouse = frappe.db.get_value('Warehouse', filters={
					'warehouse_name': _('Finished Goods'),
					'company': company
				})

				try:
					frappe.get_doc({
						'doctype': self.doctype,
						'item_code': item,
						'item_name': item,
						'description': item,
						'is_stock_item': 1,
						'item_defaults': [{
							'default_warehouse': default_warehouse,
							'company': company
						}]
					}).insert()

				except frappe.NameError:
					pass
				
def _msgprint(msg, verbose):
	if verbose:
		msgprint(msg, raise_exception=True)
	else:
		raise frappe.ValidationError(msg)


def validate_is_stock_item(item_code, is_stock_item=None, verbose=1):
	if not is_stock_item:
		is_stock_item = frappe.db.get_value("Item", item_code, "is_stock_item")

	if is_stock_item != 1:
		msg = _("Item {0} is not a stock Item").format(item_code)

		_msgprint(msg, verbose)

def on_doctype_update():
	# since route is a Text column, it needs a length for indexing
	frappe.db.add_index("Item", ["route(500)"])

	def after_insert(self):
		'''set opening stock and item price'''
		if self.opening_stock:
			self.set_opening_stock()

	def set_opening_stock(self):
		'''set opening stock'''
		if not self.is_stock_item:
			return

		if not self.valuation_rate:
			frappe.throw(_("Valuation Rate is mandatory if Opening Stock entered"))

		# default warehouse, or Stores
		for default in self.item_defaults:
			default_warehouse = (default.default_warehouse or frappe.db.get_value('Warehouse', {'warehouse_name': _('Stores')}))

			if default_warehouse:
				stock_entry = make_stock_entry(item_code=self.name, target=default_warehouse, qty=self.opening_stock,
												rate=self.valuation_rate, company=default.company)

				stock_entry.add_comment("Comment", _("Opening Stock"))

@frappe.whitelist()
def make_stock_entry(**args):
	'''Helper function to make a Stock Entry

	:item_code: Item to be moved
	:qty: Qty to be moved
	:company: Company Name (optional)
	:from_warehouse: Optional
	:to_warehouse: Optional
	:rate: Optional
	:posting_date: Optional
	:posting_time: Optional
	:do_not_save: Optional flag
	:do_not_submit: Optional flag
	'''

	s = frappe.new_doc("Stock Entry")
	args = frappe._dict(args)

	if args.posting_date or args.posting_time:
		s.set_posting_time = 1

	if args.posting_date:
		s.posting_date = args.posting_date
	if args.posting_time:
		s.posting_time = args.posting_time

	# map names
	if args.from_warehouse:
		args.source = args.from_warehouse
	if args.to_warehouse:
		args.target = args.to_warehouse
	if args.item_code:
		args.item = args.item_code

	if isinstance(args.qty, string_types):
		if '.' in args.qty:
			args.qty = flt(args.qty)
		else:
			args.qty = cint(args.qty)

	# company
	if not args.company:
		if args.source:
			args.company = frappe.db.get_value('Warehouse', args.source, 'company')
		elif args.target:
			args.company = frappe.db.get_value('Warehouse', args.target, 'company')

	# set vales from test
	if frappe.flags.in_test:
		if not args.company:
			args.company = '_Test Company'
		if not args.item:
			args.item = '_Test Item'

	s.company = args.company
	s.sales_invoice_no = args.sales_invoice_no
	s.is_opening = args.is_opening or "No"
	
	# if not args.expense_account and s.is_opening == "No":
	# 	args.expense_account = frappe.get_value('Company', s.company, 'stock_adjustment_account')

	s.append("items", {
		"item_code": args.item,
		"s_warehouse": args.source,
		"t_warehouse": args.target,
		"qty": args.qty,
		# 'expense_account': args.expense_account
	})

	# s.set_stock_entry_type()
	if not args.do_not_save:
		s.insert()
		if not args.do_not_submit:
			s.submit()
	return s
