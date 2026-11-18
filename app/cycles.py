from app.coerce import instant
from app.errors import BusinessError

CURRENT = '当前周期'
PRIOR = '旧周期'

def episodes(subject, context):
    """受试者入组周期序列，按入组时刻升序；同一入组时刻的重新入组重试只计一次。"""
    declared = context.get('cycles', {}).get(subject)
    if not declared:
        declared = [{'cycle': 1, 'enrolled': context['subjects'][subject], 'status': '在组'}]
    unique = {}
    for episode in declared:
        unique.setdefault(instant(episode['enrolled']), episode)
    return [unique[at] for at in sorted(unique)]

def current(subject, context):
    """当前周期：入组时刻最晚的周期，方案、窗口、偏离、复检共用此裁决。"""
    return episodes(subject, context)[-1]

def attribute(subject, enrolled, context):
    """按入组基准精确匹配归属周期；旧周期记录保留为证据，不顶替当前周期访视。"""
    timeline = episodes(subject, context)
    for index, episode in enumerate(timeline):
        if instant(episode['enrolled']) == enrolled:
            return {'cycle': episode.get('cycle', index + 1),
                    'cycle_role': CURRENT if index == len(timeline) - 1 else PRIOR,
                    'cycle_status': episode.get('status', '')}
    raise BusinessError('ENROLLMENT_CONFLICT', '入组基准不一致')
