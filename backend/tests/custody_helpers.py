from uuid import uuid4
from app.workspace import apply_action


def accepted_transfer(state,user,payload):
    """Explicitly send and acknowledge food before tests of subsequent sales."""
    recipient={'id':user['id'],'name':user['display_name'],'branchId':user['branch_id']}
    _,document_id=apply_action(state,{**user,'_custody_recipient':recipient},'batch.transfer',{'line':'Витрина','requestId':str(uuid4()),'recipientId':user['id'],**payload})
    apply_action(state,user,'custody.accept',{'documentId':document_id,'actualWeight':payload['weight'],'requestId':str(uuid4())})
    return document_id
