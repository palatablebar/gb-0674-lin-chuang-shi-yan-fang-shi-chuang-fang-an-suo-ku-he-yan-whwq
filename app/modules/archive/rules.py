import hashlib,json

def freeze(state):
    basis={'selected':state['selected_results'],'windows':state['windows'],'deviations':state['deviations'],'prior':state.get('prior_windows',[])}
    return {'status':'可冻结' if state['balance']['status']=='可锁库' else '待处理','seal':hashlib.sha256(json.dumps(basis,sort_keys=True).encode()).hexdigest(),'subjects':len(state['context']['subjects']),'results':len(state['selected_results']),'prior':len(state.get('prior_records',[]))}
def apply(state):
    state['archive']=freeze(state)
    prior_rows=[{k:r[k] for k in ('id','subject','visit','kind','at','enrolled','cycle','cycle_role','cycle_status')} for r in state.get('prior_records',[])]
    state['views']['archive']={'title':'冻结清单','rows':state['selected_results'],'prior_rows':prior_rows,'metrics':{'受试者':state['archive']['subjects'],'结果':state['archive']['results'],'旧周期证据':state['archive']['prior'],'状态':state['archive']['status']}}
