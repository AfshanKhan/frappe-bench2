from __future__ import unicode_literals
from frappe import _

def get_data():
	return [
		{
			"label": _("Items/Pricing and Settings"),
			"icon": "fa fa-cog",
			"items": [
				{
					"type": "doctype",
					"name": "Item",
					"onboard": 1,
				},
				{
					"type": "doctype",
					"name": "Warehouse",
					"onboard": 1,
				},
				{
					"type": "doctype",
					"name": "Brand",
					"onboard": 1,
				},
			]
		},
	]
