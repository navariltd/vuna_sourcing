app_name = "vuna_sourcing"
app_title = "Vuna Sourcing"
app_publisher = "Vuna Technologies"
app_description = "A digital self-service channel where customers and suppliers can interact with the company without relying heavily on emails, phone calls, or manual processes."
app_email = "solutions@navari.co.ke"
app_license = "mit"

# Apps
# ------------------

required_apps = ["erpnext"]

# Each item in the list will be shown as an app in the apps page
add_to_apps_screen = [
	{
		"name": "vuna_sourcing",
		"logo": "/assets/vuna_sourcing/images/sourcing-logo.png",
		"title": "Sourcing",
		"has_permission": "vuna_sourcing.api.permission.has_app_permission",
	}
]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/vuna_sourcing/css/vuna_sourcing.css"
app_include_js = "vuna_sourcing.bundle.js"

# include js, css files in header of web template
# web_include_css = "/assets/vuna_sourcing/css/vuna_sourcing.css"
# web_include_js = "/assets/vuna_sourcing/js/vuna_sourcing.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "vuna_sourcing/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
	"Request for Quotation": "overrides/client/request_for_quotation.js",
	"Supplier Quotation": "overrides/client/supplier_quotation.js",
}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "vuna_sourcing/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "vuna_sourcing.utils.jinja_methods",
# 	"filters": "vuna_sourcing.utils.jinja_filters"
# }

# Installation
# ------------

after_install = "vuna_sourcing.setup.app_setup.after_install"

# Uninstallation
# ------------

# before_uninstall = "vuna_sourcing.uninstall.before_uninstall"
# after_uninstall = "vuna_sourcing.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "vuna_sourcing.utils.before_app_install"
# after_app_install = "vuna_sourcing.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "vuna_sourcing.utils.before_app_uninstall"
# after_app_uninstall = "vuna_sourcing.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "vuna_sourcing.build.after_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "vuna_sourcing.notifications.get_notification_config"

# Awesome Bar
# -----------
# Extra search results: list of dicts with label, description, route, index.
# route: ["List", "ToDo"], "/desk/docs/some/page", or "https://example.com"
# awesomebar_search = ["vuna_sourcing.search.awesomebar_results"]

# Permissions
# -----------
# Permissions evaluated in scripted ways

PORTAL_DOCTYPES = (
	"Request for Quotation",
	"Supplier Quotation",
	"Purchase Order",
	"Purchase Invoice",
	"Quotation",
	"Sales Order",
	"Delivery Note",
	"Sales Invoice",
)

ONBOARDING_REQUEST_MODULE = (
	"vuna_sourcing.vuna_sourcing.doctype.party_onboarding_request.party_onboarding_request"
)

permission_query_conditions = {
	**{
		doctype: "vuna_sourcing.api.transactions.access.own_documents_condition"
		for doctype in PORTAL_DOCTYPES
	},
	"Supplier Quotation": [
		"vuna_sourcing.api.transactions.access.own_documents_condition",
		"vuna_sourcing.api.transactions.access.visible_quotes_condition",
	],
	"Party Onboarding Request": f"{ONBOARDING_REQUEST_MODULE}.drafts_hidden_condition",
}

has_permission = {
	**{doctype: "vuna_sourcing.api.transactions.access.is_own_document" for doctype in PORTAL_DOCTYPES},
	"Supplier Quotation": [
		"vuna_sourcing.api.transactions.access.is_own_document",
		"vuna_sourcing.api.transactions.access.is_visible_quote",
	],
	"Party Onboarding Request": f"{ONBOARDING_REQUEST_MODULE}.is_not_others_draft",
}

has_website_permission = {
	doctype: "vuna_sourcing.api.transactions.access.is_own_document" for doctype in PORTAL_DOCTYPES
}

doc_events = {
	"Request for Quotation": {
		"validate": "vuna_sourcing.overrides.server.request_for_quotation.validate",
		"before_submit": "vuna_sourcing.overrides.server.request_for_quotation.before_submit",
		"on_submit": "vuna_sourcing.overrides.server.request_for_quotation.on_submit",
	},
	"Supplier Quotation": {
		"validate": "vuna_sourcing.overrides.server.supplier_quotation.validate",
		"before_submit": "vuna_sourcing.overrides.server.supplier_quotation.validate_submittable",
		"on_submit": "vuna_sourcing.api.transactions.award.refresh_for_quotation",
		"on_cancel": "vuna_sourcing.api.transactions.award.refresh_for_quotation",
	},
	"Purchase Order": {
		"validate": "vuna_sourcing.api.transactions.award.validate_awarded_items",
	},
}

override_whitelisted_methods = {
	"erpnext.buying.doctype.supplier_quotation.supplier_quotation.make_purchase_order": (
		"vuna_sourcing.api.transactions.award.make_purchase_order"
	),
}

override_doctype_dashboards = {
	"Request for Quotation": "vuna_sourcing.overrides.server.dashboards.request_for_quotation",
	"Supplier Quotation": "vuna_sourcing.overrides.server.dashboards.supplier_quotation",
}

scheduler_events = {
	"hourly": ["vuna_sourcing.api.transactions.award.refresh_pending_selection"],
}

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"vuna_sourcing.tasks.all"
# 	],
# 	"daily": [
# 		"vuna_sourcing.tasks.daily"
# 	],
# 	"hourly": [
# 		"vuna_sourcing.tasks.hourly"
# 	],
# 	"weekly": [
# 		"vuna_sourcing.tasks.weekly"
# 	],
# 	"monthly": [
# 		"vuna_sourcing.tasks.monthly"
# 	],
# }

# Testing
# -------

before_tests = "vuna_sourcing.setup.test_setup.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "vuna_sourcing.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "vuna_sourcing.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "vuna_sourcing.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["vuna_sourcing.utils.before_request"]
# after_request = ["vuna_sourcing.utils.after_request"]

# Job Events
# ----------
# before_job = ["vuna_sourcing.utils.before_job"]
# after_job = ["vuna_sourcing.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"vuna_sourcing.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []


website_route_rules = [
	{"from_route": "/vuna-sourcing/<path:app_path>", "to_route": "vuna-sourcing"},
]
