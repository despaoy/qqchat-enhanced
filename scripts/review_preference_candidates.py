"""Interactive, resumable reviewer for DPO/ORPO preference candidates."""
from __future__ import annotations
import argparse,json
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path

def read_jsonl(path):
 return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
def atomic_write(path,rows):
 path.parent.mkdir(parents=True,exist_ok=True)
 tmp=path.with_suffix(path.suffix+".tmp")
 tmp.write_text("".join(json.dumps(x,ensure_ascii=False)+"\n" for x in rows),encoding="utf-8",newline="\n")
 tmp.replace(path)
def export_approved(path,rows):
 approved=[x for x in rows if x.get("review_status")=="approved"]
 atomic_write(path,approved);return len(approved)
def show(item,index,total):
 print("\n"+"="*88)
 print(f"[{index+1}/{total}] {item.get('id')}  category={item.get('metadata',{}).get('negative_type','unknown')}")
 print("-"*88+"\nPROMPT:\n"+item.get("prompt",""))
 print("\nCHOSEN:\n"+item.get("chosen",""))
 print("\nREJECTED:\n"+item.get("rejected",""))
 print("\nRubric:",json.dumps(item.get("rubric",{}),ensure_ascii=False))
def record(item,status,reviewer,note=""):
 item["review_status"]=status
 item["annotator"]=reviewer
 meta=item.setdefault("metadata",{})
 meta["reviewed_at"]=datetime.now(timezone.utc).isoformat()
 meta["review_note"]=note
 meta["human_reviewed"]=True
def validate(item):
 errors=[]
 if not item.get("prompt","").strip():errors.append("prompt为空")
 if not item.get("chosen","").strip():errors.append("chosen为空")
 if not item.get("rejected","").strip():errors.append("rejected为空")
 if item.get("chosen","").strip()==item.get("rejected","").strip():errors.append("chosen与rejected相同")
 if abs(sum(float(x) for x in item.get("rubric",{}).values())-1)>0.01:errors.append("rubric权重和不为1")
 return errors
def main():
 p=argparse.ArgumentParser(description="人工审核偏好对；原始候选不会被修改")
 p.add_argument("--input",type=Path,required=True)
 p.add_argument("--output",type=Path)
 p.add_argument("--reviewer",required=True)
 p.add_argument("--summary",action="store_true")
 args=p.parse_args()
 output=args.output or args.input.with_name(args.input.stem+"_reviewed.jsonl")
 rows=read_jsonl(output if output.exists() else args.input)
 if not output.exists():atomic_write(output,rows)
 approved_path=output.with_name(output.stem+"_approved.jsonl")
 if args.summary:
  print(dict(Counter(x.get("review_status","pending") for x in rows)));return
 pending=[i for i,x in enumerate(rows) if x.get("review_status","pending")=="pending"]
 if not pending:
  n=export_approved(approved_path,rows);print(f"没有待审核样本；approved={n}，导出到 {approved_path}");return
 print("判定原则：chosen必须在角色一致性/事实/安全/流畅度上明确优于rejected。")
 print("命令: a批准 r拒绝 e编辑chosen并批准 s跳过 q保存退出")
 for index in pending:
  item=rows[index];show(item,index,len(rows))
  while True:
   cmd=input("\n决定 [a/r/e/s/q]: ").strip().lower()
   if cmd=="a":
    errors=validate(item)
    if errors:print("不能批准: "+"; ".join(errors));continue
    note=input("审核备注（可空）: ").strip();record(item,"approved",args.reviewer,note);break
   if cmd=="r":
    reason=input("拒绝原因（必填）: ").strip()
    if not reason:print("请填写原因");continue
    record(item,"rejected",args.reviewer,reason);break
   if cmd=="e":
    print("请输入修正后的chosen（单行；取消请输入空行）:")
    value=input().strip()
    if not value:continue
    item["chosen"]=value
    errors=validate(item)
    if errors:print("修正后仍不能批准: "+"; ".join(errors));continue
    note=input("修改说明（必填）: ").strip()
    if not note:print("必须记录修改说明");continue
    record(item,"approved",args.reviewer,"edited: "+note);break
   if cmd=="s":break
   if cmd=="q":
    atomic_write(output,rows);n=export_approved(approved_path,rows)
    print(f"已保存。approved={n}，审核文件={output}，训练文件={approved_path}");return
   print("未知命令")
  atomic_write(output,rows);export_approved(approved_path,rows)
 counts=Counter(x.get("review_status","pending") for x in rows)
 n=export_approved(approved_path,rows)
 print(f"审核完成: {dict(counts)}；approved训练文件({n})={approved_path}")
if __name__=="__main__":main()
