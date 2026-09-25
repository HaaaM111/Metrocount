# -*- coding: utf-8 -*-
import io, re
svg = io.open('static/subway/maps/shmetro-map.svg', encoding='utf-8').read()
svg = svg.replace('<?xml version="1.0" encoding="UTF-8"?>', '').strip()
# inline: CSS/JS 控制尺寸（fit 整图 / full 放大），preserveAspectRatio 等比居中
svg = svg.replace('<svg ', '<svg style="display:block;width:100%;height:auto" preserveAspectRatio="xMidYMid meet" ', 1)
html = io.open('templates/subway/index.html', encoding='utf-8').read()
pattern = re.compile(r'<svg[^>]*>.*?</svg>', re.S)
assert pattern.search(html), 'existing svg block not found'
html = pattern.sub(svg, html, count=1)
io.open('templates/subway/index.html', 'w', encoding='utf-8').write(html)
print('re-inlined, new size', len(html))
