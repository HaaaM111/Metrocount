# -*- coding: utf-8 -*-
import io, re
svg = io.open('static/subway/maps/shmetro-map.svg', encoding='utf-8').read()
svg = svg.replace('<?xml version="1.0" encoding="UTF-8"?>', '').strip()
# inline: CSS/JS 控制尺寸（fit 整图 / full 放大），preserveAspectRatio 等比居中
svg = svg.replace('<svg ', '<svg style="display:block;width:100%;height:auto" preserveAspectRatio="xMidYMid meet" ', 1)
# SVG 抽到共享片段，首页与全屏页 {% include %} 同一份
io.open('templates/subway/_map_svg.html', 'w', encoding='utf-8').write(svg)
print('re-inlined into _map_svg.html, size', len(svg))
