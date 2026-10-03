# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt


from vuna_sourcing.api.permission import create_portal_user_role


def after_install() -> None:
	create_portal_user_role()
