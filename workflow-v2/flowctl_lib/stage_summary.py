"""Read-only presentation of stage lifecycle; not an approval mechanism."""


def stage_summary(state):
    stage = state.get('current_stage')
    action = state.get('pending_action') or ''
    signal = state.get('pending_signal') or {}
    result = None
    if signal.get('signal') == 'FLOW_RUN_ROUTE_BACK':
        result = '拒绝'
    elif action.startswith('revise:'):
        key = stage.removeprefix('flow-') if stage else ''
        if key in {'spec', 'plan', 'code', 'integration'}:
            key += ':' + str(state.get('active_milestone') or '')
        artifact = state.get('artifacts', {}).get(key, {})
        if any(attempt.get('artifact_key') == key and attempt.get('status') == 'FAILED'
               and attempt.get('classification') == 'REVIEW_RESULT'
               and attempt.get('eligible', True)
               and attempt.get('artifact_digest') == artifact.get('digest')
               for attempt in state.get('reviews', {}).get('attempts', {}).values()):
            result = '拒绝'
    if signal.get('signal') in {'FLOW_RUN_BLOCKED', 'FLOW_ADMISSION_BLOCKED'} or action.startswith('blocked'):
        status = '阻塞中'
        explanation = signal.get('cause') or action or '存在明确障碍'
    elif signal.get('signal') in {'FLOW_RUN_HUMAN_GATE', 'FLOW_ADMISSION_GATE'} or action == 'human_gate':
        status = '等待中'
        explanation = '等待人工：' + str(signal.get('gate') or signal.get('cause') or '输入或确认')
    elif stage == 'complete':
        status = '已完成'
        result = '有条件通过' if state.get('open_gaps') else '通过'
        explanation = '流程交接已完成；遗留问题见 open_gaps' if state.get('open_gaps') else '流程交接已完成'
    elif stage:
        status, explanation = '进行中', action or '阶段执行中'
        if signal.get('cause'):
            explanation = str(signal['cause'])
    else:
        status, explanation = None, '尚未开始'
    if signal.get('resume_condition'):
        explanation += '；恢复条件：' + str(signal['resume_condition'])
    summary = {'status': status, 'result': result, 'explanation': explanation}
    if stage:
        summary.update(stage=stage, milestone_id=state.get('active_milestone')
                       if stage in {'flow-spec', 'flow-plan', 'flow-code', 'flow-integration'} else None)
    return summary
