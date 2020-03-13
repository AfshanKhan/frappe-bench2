# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
# import frappe
from frappe.model.document import Document

class Item(Document):
	# pass
	def before_insert(self):
		if not self.description:
			self.description = self.item_name

	def validate(self):
		super(Item, self).validate()

		if not self.item_name:
			self.item_name = self.item_code

		if not self.description:
			self.description = self.item_name

		# self.validate_description()
		# self.validate_warehouse_for_reorder()

		self.cant_change()

	# def validate_description(self):
	# 	'''Clean HTML description if set'''
	# 	if cint(frappe.db.get_single_value('Stock Settings', 'clean_description_html')):
	# 		self.description = clean_html(self.description)

	# def validate_warehouse_for_reorder(self):
	# 	'''Validate Reorder level table for duplicate and conditional mandatory'''
	# 	warehouse = []
	# 	for d in self.get("reorder_levels"):
	# 		if not d.warehouse_group:
	# 			d.warehouse_group = d.warehouse
	# 		if d.get("warehouse") and d.get("warehouse") not in warehouse:
	# 			warehouse += [d.get("warehouse")]
	# 		else:
	# 			frappe.throw(_("Row {0}: An Reorder entry already exists for this warehouse {1}")
	# 								.format(d.idx, d.warehouse), DuplicateReorderRows)

	# 		if d.warehouse_reorder_level and not d.warehouse_reorder_qty:
	# 			frappe.throw(_("Row #{0}: Please set reorder quantity").format(d.idx))

	def cant_change(self):
		if not self.get("__islocal"):
			fields = ("is_stock_item", "valuation_method")

			values = frappe.db.get_value("Item", self.name, fields, as_dict=True)
			# if not values.get('valuation_method') and self.get('valuation_method'):
			# 	values['valuation_method'] = frappe.db.get_single_value("Stock Settings", "valuation_method") or "FIFO"

			if values:
				for field in fields:
					if cstr(self.get(field)) != cstr(values.get(field)):
						if not self.check_if_linked_document_exists(field):
							break # no linked document, allowed
						else:
							frappe.throw(_("As there are existing transactions against item {0}, you can not change the value of {1}").format(self.name, frappe.bold(self.meta.get_label(field))))

	# def on_update(self):
		# invalidate_cache_for_item(self)
		# self.validate_name_with_item_group()
		# self.update_variants()
		# self.update_item_price()
		# self.update_template_item()

	# def update_item_price(self):
	# 	frappe.db.sql("""update `tabItem Price` set item_name=%s,
	# 		item_description=%s, brand=%s where item_code=%s""",
	# 				(self.item_name, self.description, self.brand, self.name))

	# def on_trash(self):
		# pass
		# super(Item, self).on_trash()
		# frappe.db.sql("""delete from tabBin where item_code=%s""", self.name)
		# frappe.db.sql("delete from `tabItem Price` where item_code=%s", self.name)
		# for variant_of in frappe.get_all("Item", filters={"variant_of": self.name}):
		# 	frappe.delete_doc("Item", variant_of.name)

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
			# invalidate_cache_for_item(self)
			clear_cache(self.route)

		frappe.db.set_value("Item", new_name, "item_code", new_name)

		# if merge:
		# 	# self.set_last_purchase_rate(new_name)
		# 	self.recalculate_bin_qty(new_name)


	# def recalculate_bin_qty(self, new_name):
	# 	from erpnext.stock.stock_balance import repost_stock
	# 	frappe.db.auto_commit_on_many_writes = 1
	# 	existing_allow_negative_stock = frappe.db.get_value("Stock Settings", None, "allow_negative_stock")
	# 	frappe.db.set_value("Stock Settings", None, "allow_negative_stock", 1)

	# 	repost_stock_for_warehouses = frappe.db.sql_list("""select distinct warehouse
	# 		from tabBin where item_code=%s""", new_name)

	# 	# Delete all existing bins to avoid duplicate bins for the same item and warehouse
	# 	frappe.db.sql("delete from `tabBin` where item_code=%s", new_name)

	# 	for warehouse in repost_stock_for_warehouses:
	# 		repost_stock(new_name, warehouse)

	# 	frappe.db.set_value("Stock Settings", None, "allow_negative_stock", existing_allow_negative_stock)
	# 	frappe.db.auto_commit_on_many_writes = 0

	def check_if_linked_document_exists(self, field):
		linked_doctypes = ["Delivery Note Item", "Sales Invoice Item", "Purchase Receipt Item",
			"Purchase Invoice Item", "Stock Entry Detail", "Stock Reconciliation Item"]

		# For "Is Stock Item", following doctypes is important
		# because reserved_qty, ordered_qty and requested_qty updated from these doctypes
		if field == "is_stock_item":
			linked_doctypes += ["Sales Order Item", "Purchase Order Item", "Material Request Item"]

		for doctype in linked_doctypes:
			if frappe.db.get_value(doctype, filters={"item_code": self.name, "docstatus": 1}) or \
				frappe.db.get_value("Production Order",
					filters={"production_item": self.name, "docstatus": 1}):
				return True

	def create_onboarding_docs(self, args):
		# company = frappe.defaults.get_defaults().get('company') or \
		# 	frappe.db.get_single_value('Global Defaults', 'default_company')

		for i in range(1, args.get('max_count')):
			item = args.get('item_' + str(i))
			if item:
				# default_warehouse = ''
				# default_warehouse = frappe.db.get_value('Warehouse', filters={
				# 	'warehouse_name': _('Finished Goods'),
				# 	# 'company': company
				# })

				try:
					frappe.get_doc({
						'doctype': self.doctype,
						'item_code': item,
						'item_name': item,
						'description': item,
						# 'show_in_website': 1,
						# 'is_sales_item': 1,
						# 'is_purchase_item': 1,
						'is_stock_item': 1,
						# 'item_group': _('Products'),
						# 'stock_uom': _(args.get('item_uom_' + str(i))),
						# 'item_defaults': [{
						# 	'default_warehouse': default_warehouse,
						# 	'company': company
						# }]
					}).insert()

				except frappe.NameError:
					pass
				# else:
				# 	if args.get('item_price_' + str(i)):
				# 		item_price = flt(args.get('item_price_' + str(i)))

				# 		price_list_name = frappe.db.get_value('Price List', {'selling': 1})
				# 		make_item_price(item, price_list_name, item_price)
				# 		price_list_name = frappe.db.get_value('Price List', {'buying': 1})
				# 		make_item_price(item, price_list_name, item_price)

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

def get_timeline_data(doctype, name):
	'''returns timeline data based on stock ledger entry'''
	out = {}
	items = dict(frappe.db.sql('''select posting_date, count(*)
		from `tabStock Ledger Entry` where item_code=%s
			and posting_date > date_sub(curdate(), interval 1 year)
			group by posting_date''', name))

	for date, count in iteritems(items):
		timestamp = get_timestamp(date)
		out.update({timestamp: count})

	return out

def on_doctype_update():
	# since route is a Text column, it needs a length for indexing
	frappe.db.add_index("Item", ["route(500)"])

	# def after_insert(self):
	# 	'''set opening stock and item price'''
	# 	# if self.standard_rate:
	# 	# 	for default in self.item_defaults or [frappe._dict()]:
	# 	# 		self.add_price(default.default_price_list)

	# 	if self.opening_stock:
	# 		self.set_opening_stock()

	# def set_opening_stock(self):
	# 	'''set opening stock'''
	# 	if not self.is_stock_item or self.has_serial_no or self.has_batch_no:
	# 		return

	# 	# if not self.valuation_rate and self.standard_rate:
	# 	# 	self.valuation_rate = self.standard_rate

	# 	if not self.valuation_rate:
	# 		frappe.throw(_("Valuation Rate is mandatory if Opening Stock entered"))

	# 	# from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry

	# 	# # default warehouse, or Stores
	# 	# for default in self.item_defaults or [frappe._dict({'company': frappe.defaults.get_defaults().company})]:
	# 	# 	default_warehouse = (default.default_warehouse
	# 	# 			or frappe.db.get_single_value('Stock Settings', 'default_warehouse')
	# 	# 			or frappe.db.get_value('Warehouse', {'warehouse_name': _('Stores')}))

	# 	# 	if default_warehouse:
	# 	# 		stock_entry = make_stock_entry(item_code=self.name, target=default_warehouse, qty=self.opening_stock,
	# 	# 										rate=self.valuation_rate, company=default.company)

	# 	# 		stock_entry.add_comment("Comment", _("Opening Stock"))
