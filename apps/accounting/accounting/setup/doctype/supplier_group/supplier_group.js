// Copyright (c) 2020, Frappe and contributors
// For license information, please see license.txt

frappe.ui.form.on('Supplier Group', {
	// refresh: function(frm) {

	// }
});

cur_frm.cscript.refresh = function(doc) {
	cur_frm.set_intro(doc.__islocal ? "" : __("There is nothing to edit."));
	cur_frm.cscript.set_root_readonly(doc);
};

cur_frm.cscript.set_root_readonly = function(doc) {
	// read-only for root customer group
	if(!doc.parent_supplier_group) {
		cur_frm.set_read_only();
		cur_frm.set_intro(__("This is a root supplier group and cannot be edited."));
	} else {
		cur_frm.set_intro(null);
	}
};

// get query select Customer Group
cur_frm.fields_dict['parent_supplier_group'].get_query = function() {
	return {
		filters: {
			'is_group': 1
		}
	};
};