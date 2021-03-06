// Copyright (c) 2016, Frappe and contributors
// For license information, please see license.txt
/* eslint-disable */


frappe.query_reports["General Ledger"] = {
	"filters": [
		{
			"fieldname":"company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"default": frappe.defaults.get_user_default("Company"),
			"reqd": 1
		},
		{
			"fieldname":"from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.add_months(frappe.datetime.get_today(), -1),
			"reqd": 1,
			"width": "60px"
		},
		{
			"fieldname":"to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today(),
			"reqd": 1,
			"width": "60px"
		},
		{
			"fieldname":"account",
			"label": __("Account"),
			"fieldtype": "Link",
			"options": "Account",
			"get_query": function() {
				var company = frappe.query_report.get_filter_value('company');
				return {
					"doctype": "Account",
					"filters": {
						"company": company,
					}
				}
			}
		},
		{
			"fieldname":"voucher_no",
			"label": __("Voucher No"),
			"fieldtype": "Data",
			on_change: function() {
				frappe.query_report.set_filter_value('group_by', "");
			}
		},
		{
			"fieldtype": "Break",
		},
		{
			"fieldname":"party_type",
			"label": __("Party Type"),
			"fieldtype": "Link",
			"options": "Party Type",
			"default": "",
			on_change: function() {
				frappe.query_report.set_filter_value('party', "");
			}
		},
		{
			"fieldname":"party",
			"label": __("Party"),
			"fieldtype": "MultiSelectList",
			get_data: function(txt) {
				if (!frappe.query_report.filters) return;

				let party_type = frappe.query_report.get_filter_value('party_type');
				if (!party_type) return;

				return frappe.db.get_link_options(party_type, txt);
			},
			on_change: function() {
				var party_type = frappe.query_report.get_filter_value('party_type');
				var parties = frappe.query_report.get_filter_value('party');

				if(!party_type || parties.length === 0 || parties.length > 1) {
					frappe.query_report.set_filter_value('party_name', "");
					// frappe.query_report.set_filter_value('tax_id', "");
					return;
				} else {
					var party = parties[0];
					var fieldname = erpnext.utils.get_party_name(party_type) || "name";
					frappe.db.get_value(party_type, party, fieldname, function(value) {
						frappe.query_report.set_filter_value('party_name', value[fieldname]);
					});

					// if (party_type === "Customer" || party_type === "Supplier") {
					// 	frappe.db.get_value(party_type, party, "tax_id", function(value) {
					// 		frappe.query_report.set_filter_value('tax_id', value["tax_id"]);
					// 	});
					// }
				}
			}
		},
		{
			"fieldname":"party_name",
			"label": __("Party Name"),
			"fieldtype": "Data",
			"hidden": 1
		},
		{
			"fieldname":"group_by",
			"label": __("Group by"),
			"fieldtype": "Select",
			"options": ["", __("Group by Voucher"), __("Group by Voucher (Consolidated)"),
				__("Group by Account"), __("Group by Party")],
			"default": __("Group by Voucher (Consolidated)")
		},
		// {
		// 	"fieldname":"tax_id",
		// 	"label": __("Tax Id"),
		// 	"fieldtype": "Data",
		// 	"hidden": 1
		// },
		// {
		// 	"fieldname": "presentation_currency",
		// 	"label": __("Currency"),
		// 	"fieldtype": "Select",
		// 	"options": erpnext.get_presentation_currency_list()
		// },
		// {
		// 	"fieldname":"cost_center",
		// 	"label": __("Cost Center"),
		// 	"fieldtype": "MultiSelectList",
		// 	get_data: function(txt) {
		// 		return frappe.db.get_link_options('Cost Center', txt);
		// 	}
		// },
		// {
		// 	"fieldname":"project",
		// 	"label": __("Project"),
		// 	"fieldtype": "MultiSelectList",
		// 	get_data: function(txt) {
		// 		return frappe.db.get_link_options('Project', txt);
		// 	}
		// },
		{
			"fieldname": "show_opening_entries",
			"label": __("Show Opening Entries"),
			"fieldtype": "Check"
		},
		{
			"fieldname": "include_default_book_entries",
			"label": __("Include Default Book Entries"),
			"fieldtype": "Check",
			"default": 1
		}
	]
}

accounting.dimension_filters.forEach((dimension) => {
	frappe.query_reports["General Ledger"].filters.splice(15, 0 ,{
		"fieldname": dimension["fieldname"],
		"label": __(dimension["label"]),
		"fieldtype": "Link",
		"options": dimension["document_type"]
	});
});


__('Address needs to be linked to a Company.' , null, "this is the context")

__('Address needs to be linked to a Company.{0} {1}' , ['a', 'b'])

_("Address needs to be linked to a Company.{0}", context="this is the context").format('asdf', 'adsf')

_('Welcome %s, get started with ERPNext in just a few clicks.' % full_name)

frappe.ui.form.on('Google Settings', {
	refresh: function(frm) {
		frm.dashboard.set_headline(__("For more information, {0}.", [`<a href='https://erpnext.com/docs/user/manual/en/erpnext_integration/google_settings'>${__('Click here')}</a>`]));
	}
});

frappe.ui.form.on('Google Settings', {
	refresh: function(frm) {
		frm.dashboard.set_headline(__("For more information, {0}.", [`<a href='https://erpnext.com/docs/user/manual/en/erpnext_integration/google_settings'>${__('Click here')}</a>`]));
	}
});

_('Welcome %s, get started with ERPNext in just a few clicks.' % full_name)

_('Welcome %s, get started with ERPNext in just a few clicks.' % full_name)
_('Welcome %s, get started with ERPNext in just a few clicks.' % full_name)
_('Welcome %s, get started with ERPNext in just a few clicks.' % full_name)
_('Welcome %s, get started with ERPNext in just a few clicks.' % full_name)
_('Welcome %s, get started with ERPNext in just a few clicks.' % full_name)
