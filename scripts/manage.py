"""Create institutional accounts with a hidden password prompt, never command-line credentials."""
import argparse
import getpass
import secrets
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sqlalchemy import delete
from apps.api.auth import PERMISSIONS,password_hash
from apps.api.storage import Store,accounts,auth_tokens


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=['create-account','revoke-sessions'])
    parser.add_argument('--organization',required=True)
    parser.add_argument('--username',required=True)
    parser.add_argument('--role',choices=list(PERMISSIONS),default='participant')
    parser.add_argument('--person-id')
    args=parser.parse_args()
    store=Store()
    if args.operation=='create-account':
        if args.role=='participant' and not args.person_id:
            parser.error('참가자는 --person-id가 필요합니다.')
        password=getpass.getpass('새 계정 비밀번호 (12자 이상): ')
        confirm=getpass.getpass('비밀번호 재입력: ')
        if len(password)<12 or password!=confirm:
            parser.error('12자 이상이며 두 입력이 같아야 합니다.')
        identity={'id':args.username,'name':args.username,'role':args.role,'organization_id':args.organization,'person_id':args.person_id,'synthetic_only':False}
        with store.engine.begin() as conn:
            conn.execute(accounts.insert().values(organization_id=args.organization,username=args.username,password_hash=password_hash(password),identity=identity))
            store.log(conn,args.organization,'local-operator','ACCOUNT_CREATED',args.username)
        print('기관 계정을 생성했습니다. 비밀번호는 저장 출력하지 않습니다.')
    else:
        with store.engine.begin() as conn:
            rows=conn.execute(auth_tokens.select()).mappings().all()
            hashes=[r['token_hash'] for r in rows if r['identity']['organization_id']==args.organization and r['identity']['id']==args.username]
            if hashes:
                conn.execute(delete(auth_tokens).where(auth_tokens.c.token_hash.in_(hashes)))
            store.log(conn,args.organization,'local-operator','SESSIONS_REVOKED',args.username)
        print(f'서버 세션 {len(hashes)}개를 철회했습니다.')
    store.engine.dispose()


if __name__=='__main__':main()
