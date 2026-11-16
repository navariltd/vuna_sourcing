# Contributing to Vuna Sourcing

## Production Setup

### Managed Hosting

Vuna Sourcing can be deployed on [Frappe Cloud](https://frappecloud.com/). In your bench group, click **Apps → Add App → Add from GitHub**, enter `https://github.com/navariltd/vuna_sourcing`, deploy, then install the app on your site.

### Self Hosting

```bash
bench get-app https://github.com/navariltd/vuna_sourcing --branch develop
bench --site [your-site] install-app vuna_sourcing
bench build --app vuna_sourcing
bench restart
```

## Development Setup

### Manual Installation

1. Set up a Frappe bench (version 16) by following the [Frappe installation guide](https://docs.frappe.io/framework/user/en/installation), then start it:

   ```bash
   bench start
   ```

2. In another terminal, create a site:

   ```bash
   bench new-site sourcing.localhost
   bench --site sourcing.localhost set-config developer_mode 1
   ```

3. Install ERPNext:

   ```bash
   bench get-app erpnext --branch version-16
   bench --site sourcing.localhost install-app erpnext
   ```

4. Get and install Vuna Sourcing:

   ```bash
   bench get-app https://github.com/navariltd/vuna_sourcing --branch develop
   bench --site sourcing.localhost install-app vuna_sourcing
   ```

5. Build the assets and migrate:

   ```bash
   bench build --app vuna_sourcing
   bench --site sourcing.localhost migrate
   ```

6. Open the site, finish the ERPNext setup wizard in Desk, then open the portal:

   ```text
   http://sourcing.localhost:8000/app
   http://sourcing.localhost:8000/vuna-sourcing
   ```

### Portal Development

To work on the portal with live reload, run the Vite dev server while `bench start` is running:

```bash
cd apps/vuna_sourcing
npm install
npm run dev
```

### Running Tests

```bash
bench --site sourcing.localhost set-config allow_tests true
bench --site sourcing.localhost run-tests --app vuna_sourcing
```

## Contributing

This project uses `pre-commit` for formatting and linting. Install and enable it inside the repository:

```bash
cd apps/vuna_sourcing
pre-commit install
```

The configured checks are:

* ruff
* eslint
* prettier
* pyupgrade
