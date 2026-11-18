def decide(state):
    c=state['counts'];prior=len(state.get('prior_records',[]))
    explained=len(state['records'])+prior+len(state['quarantine'])+c['blank']+c['duplicate']+c['repeated_header'];blocked=len(state['deviations'])+len(state['retest_issues'])+len(state['quarantine'])
    return {'input':c['input'],'accepted':len(state['records'])+prior,'prior':prior,'quarantined':len(state['quarantine']),'row_balanced':c['input']==explained,'completed':len(state['completed']),'expected':len(state['context']['subjects'])*len(state['context']['required_visits']),'deviations':len(state['deviations']),'retest_issues':len(state['retest_issues']),'blocked':blocked,'status':'可锁库' if not blocked and c['input']==explained else '待处理'}
def apply(state):
    state['balance']=decide(state)
    prior_rows=[{k:r[k] for k in ('id','subject','visit','kind','at','enrolled','cycle','cycle_role','cycle_status')} for r in state.get('prior_records',[])]
    state['views']['locking']={'title':'锁库闸门','rows':[state['balance']],'prior_rows':prior_rows,'metrics':{'应访视':state['balance']['expected'],'已完成':state['balance']['completed'],'阻断项':state['balance']['blocked'],'旧周期记录':len(prior_rows)}}
