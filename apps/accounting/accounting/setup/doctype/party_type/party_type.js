// Copyright (c) 2020, Frappe and contributors
// For license information, please see license.txt

frappe.ui.form.on('Party Type', {
	// refresh: function(frm) {

	// }
	setup: function(frm) {
		frm.fields_dict["party_type"].get_query = function(frm) {
			return {
				filters: {
					"istable": 0,
					"is_submittable": 0
				}
			}
		}
	}
});
