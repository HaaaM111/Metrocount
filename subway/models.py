from django.db import models


class Line(models.Model):
    name = models.CharField(max_length=40, unique=True, verbose_name='线路名称')
    code = models.CharField(max_length=12, unique=True, verbose_name='线路编号')
    color = models.CharField(max_length=7, default='#1677ff', verbose_name='线路颜色')

    class Meta:
        ordering = ['code']
        verbose_name = '地铁线路'
        verbose_name_plural = '地铁线路'

    def __str__(self):
        return self.name


class Station(models.Model):
    name = models.CharField(max_length=60, verbose_name='站点名称')
    line = models.ForeignKey(Line, on_delete=models.CASCADE, related_name='stations', verbose_name='所属线路')
    sequence = models.PositiveIntegerField(verbose_name='线路顺序')
    x = models.PositiveIntegerField(default=50, verbose_name='地图 X 百分比')
    y = models.PositiveIntegerField(default=50, verbose_name='地图 Y 百分比')
    is_transfer = models.BooleanField(default=False, verbose_name='是否换乘站')

    class Meta:
        ordering = ['line__code', 'sequence']
        constraints = [
            models.UniqueConstraint(fields=['line', 'sequence'], name='unique_line_sequence'),
        ]
        verbose_name = '地铁站点'
        verbose_name_plural = '地铁站点'

    def __str__(self):
        return f'{self.name}({self.line.name})'


class Edge(models.Model):
    """Inter-station edge with travel time (minutes).
    For transfer edges, line is '换乘' and travel_time is ~5 min.
    """
    from_station = models.ForeignKey(Station, on_delete=models.CASCADE, related_name='out_edges', verbose_name='起点站')
    to_station = models.ForeignKey(Station, on_delete=models.CASCADE, related_name='in_edges', verbose_name='终点站')
    line = models.ForeignKey(Line, on_delete=models.CASCADE, verbose_name='所属线路')
    travel_time = models.PositiveIntegerField(verbose_name='通行时间(分钟)')
    distance_km = models.FloatField(null=True, blank=True, verbose_name='真实站间距(公里)')

    class Meta:
        verbose_name = '站间边'
        verbose_name_plural = '站间边'

    def __str__(self):
        return f'{self.from_station} -> {self.to_station} ({self.travel_time}min)'
