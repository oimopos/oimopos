FROM nginx:1.27-alpine

COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY index.html admin.html login.html platform.html numeric-inputs.js app.js admin.js company-settings.js catalog-cover.js ingredients-list.js ingredient-picker.js product-variants.js custody.js oimo.css minimal.css auth.js api-client.js platform.js styles.css admin.css auth.css platform.css /usr/share/nginx/html/
COPY tests /usr/share/nginx/html/tests
COPY docs/program-process-flow.html /usr/share/nginx/html/docs/program-process-flow.html

EXPOSE 80
