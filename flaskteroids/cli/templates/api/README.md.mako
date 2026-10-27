<%inherit file="/README.md.mako"/>\
<%block name="system_test_command"/>
<%block name="browser_guidance">
This is an API-only application. Scaffolds generate JSON CRUD and request tests,
without browser views or assets. Cookie authentication and session opt-ins are not
provided by this mode. See [API-only applications](https://nullco.github.io/flaskteroids/controllers/api/).
</%block>