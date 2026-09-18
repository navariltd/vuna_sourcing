import preset, { content } from "frappe-ui/tailwind";

export default {
	presets: [preset],
	// Tailwind v3 doesn't merge preset content, so spread frappe-ui's paths in
	content: [...content, "./index.html", "./src/**/*.{vue,js,ts,jsx,tsx}"],
};
