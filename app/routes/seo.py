from flask import Blueprint, Response

bp = Blueprint('seo', __name__)

@bp.route('/sitemap.xml')
def sitemap():
    xml = '''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://allowance-app-98k3.onrender.com/</loc>
    <changefreq>weekly</changefreq>
    <priority>1.0</priority>
  </url>
  <url>
    <loc>https://allowance-app-98k3.onrender.com/register/</loc>
    <changefreq>monthly</changefreq>
    <priority>0.9</priority>
  </url>
  <url>
    <loc>https://allowance-app-98k3.onrender.com/auth/login</loc>
    <changefreq>monthly</changefreq>
    <priority>0.5</priority>
  </url>
</urlset>'''
    return Response(xml, mimetype='application/xml')

@bp.route('/robots.txt')
def robots():
    txt = '''User-agent: *
Allow: /
Allow: /register/
Disallow: /admin/
Disallow: /billing/webhook
Sitemap: https://allowance-app-98k3.onrender.com/sitemap.xml'''
    return Response(txt, mimetype='text/plain')
