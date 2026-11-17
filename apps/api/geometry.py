"""Bounded synthetic plan geometry. These checks do not certify a real building."""
import math


def validate_outline(points):
    if not points:
        return points
    if not 3 <= len(points) <= 100 or any(len(p) != 2 or any(not math.isfinite(v) or abs(v) > 300 for v in p) for p in points):
        raise ValueError('윤곽은 범위 내 유한 2차원 좌표 3~100개여야 합니다.')
    size = len(points)
    if any(math.dist(points[i], points[(i + 1) % size]) < .01 for i in range(size)):
        raise ValueError('윤곽에 길이가 없는 변이 있습니다. 마지막 점을 중복하지 마세요.')

    def cross(a, b, c):
        return (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])

    def on_segment(a, b, p):
        return abs(cross(a, b, p)) < 1e-8 and min(a[0],b[0])-1e-8 <= p[0] <= max(a[0],b[0])+1e-8 and min(a[1],b[1])-1e-8 <= p[1] <= max(a[1],b[1])+1e-8

    for i in range(size):
        a, b = points[i], points[(i+1) % size]
        for j in range(i+1, size):
            if j == i+1 or (i == 0 and j == size-1):
                continue
            c, d = points[j], points[(j+1) % size]
            if (cross(a,b,c)*cross(a,b,d) < 0 and cross(c,d,a)*cross(c,d,b) < 0) or any((on_segment(a,b,c),on_segment(a,b,d),on_segment(c,d,a),on_segment(c,d,b))):
                raise ValueError('윤곽이 자기 교차하거나 서로 닿습니다.')
    if abs(sum(points[i][0]*points[(i+1) % size][1] - points[(i+1) % size][0]*points[i][1] for i in range(size))) / 2 < 4:
        raise ValueError('윤곽 면적이 너무 작습니다.')
    return points
