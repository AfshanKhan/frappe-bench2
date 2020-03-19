// Copyright (c) 2020, Frappe and contributors
// For license information, please see license.txt

frappe.ui.form.on('Supplier', {
	// refresh: function(frm) {

	// }

	setup: function (frm) {
		frm.set_query('account', 'accounts', function (doc, cdt, cdn) {
			var d = locals[cdt][cdn];
			return {
				filters: {
					'account_type': 'Payable',
					"is_group": 0
				}
			}
		});
	},
	refresh: function (frm) {
		frappe.dynamic_link = { doc: frm.doc, fieldname: 'name', doctype: 'Supplier' }

		if (frappe.defaults.get_default("supp_master_name") != "Naming Series") {
			frm.toggle_display("naming_series", false);
		}
		if (frm.doc.__islocal) {
			hide_field(['address_html','contact_html']);
			frappe.contacts.clear_address_and_contact(frm);
		}
		else {
			unhide_field(['address_html','contact_html']);
			frappe.contacts.render_address_and_contact(frm);

			// custom buttons
		// 	frm.add_custom_button(__('Accounting Ledger'), function () {
		// 		frappe.set_route('query-report', 'General Ledger',
		// 			{ party_type: 'Supplier', party: frm.doc.name });
		// 	}, __("View"));

		// 	frm.add_custom_button(__('Accounts Payable'), function () {
		// 		frappe.set_route('query-report', 'Accounts Payable', { supplier: frm.doc.name });
		// 	}, __("View"));


		}
	},

});
