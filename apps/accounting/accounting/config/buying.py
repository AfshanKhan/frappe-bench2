from __future__ import unicode_literals
from frappe import _

def get_data():
	return [
		{
			"label": _("Purchasing"),
			"icon": "fa fa-star",
			"items": [
				{
					"type": "doctype",
					"name": "Item",
					"onboard": 1,
					"description": _("All Products or Services."),
				},
				{
					"type": "doctype",
					"name": "Purchase Invoice",
					"onboard": 1,
					"dependencies": ["Item", "Supplier"]
				},
				{
					"type": "doctype",
					"name": "Payment Entry",
					"description": _("Cash transactions against party")
				},
			]
		},
		{
			"label": _("Supplier"),
			"items": [
				{
					"type": "doctype",
					"name": "Supplier",
					"onboard": 1,
					"description": _("Supplier database."),
				},
				{
					"type": "doctype",
					"name": "Supplier Group",
					"description": _("Supplier Group master.")
				},
				{
					"type": "doctype",
					"name": "Contact",
					"description": _("All Contacts."),
				},
				{
					"type": "doctype",
					"name": "Address",
					"description": _("All Addresses."),
				},

			]
		}
	]
