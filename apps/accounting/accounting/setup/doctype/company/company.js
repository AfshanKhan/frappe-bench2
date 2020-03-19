// Copyright (c) 2020, Frappe and contributors
// For license information, please see license.txt


// frappe.provide("accounting.company");

frappe.ui.form.on('Company', {
	// refresh: function(frm) {

	// }

	company_name: function(frm) {
		if(frm.doc.__islocal) {
			// add missing " " arg in split method
			let parts = frm.doc.company_name.split(" ");
			let abbr = $.map(parts, function (p) {
				return p? p.substr(0, 1) : null;
			}).join("");
			frm.set_value("abbr", abbr);
		}
	},

	refresh: function(frm) {
		if(!frm.doc.__islocal) {
			frm.doc.abbr && frm.set_df_property("abbr", "read_only", 1);
		// }
		// if(!frm.doc.__islocal) {
		frappe.dynamic_link = {doc: frm.doc, fieldname: 'name', doctype: 'Company'}

		frm.add_custom_button(__('Chart of Accounts'), function() {
			frappe.set_route('Tree', 'Account', {'company': frm.doc.name})
		}, __("View"));
	}
	},

});

cur_frm.cscript.change_abbr = function() {
	var dialog = new frappe.ui.Dialog({
		title: "Replace Abbr",
		fields: [
			{"fieldtype": "Data", "label": "New Abbreviation", "fieldname": "new_abbr",
				"reqd": 1 },
			{"fieldtype": "Button", "label": "Update", "fieldname": "update"},
		]
	});

	dialog.fields_dict.update.$input.click(function() {
		var args = dialog.get_values();
		if(!args) return;
		frappe.show_alert(__("Update in progress. It might take a while."));
		return frappe.call({
			method: "accounting.setup.doctype.company.company.enqueue_replace_abbr",
			args: {
				"company": cur_frm.doc.name,
				"old": cur_frm.doc.abbr,
				"new": args.new_abbr
			},
			callback: function(r) {
				if(r.exc) {
					frappe.msgprint(__("There were errors."));
					return;
				} else {
					cur_frm.set_value("abbr", args.new_abbr);
				}
				dialog.hide();
				cur_frm.refresh();
			},
			btn: this
		})
	});
	dialog.show();
}