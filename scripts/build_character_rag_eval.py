"""Convert held-out character RAG samples to the existing retrieval experiment schema."""
import json
from pathlib import Path
R=Path(__file__).resolve().parents[1];E=R/"backend/data/character_dialogues/experiments";O=E/"research"
def load(p):return json.loads(p.read_text(encoding="utf-8"))
def main():
 docs=[];questions=[]
 for key in ("shenbai_mizunamo","tsukiyashiro_kisaki"):
  ds=load(E/f"{key}_eval.json")["prompts"];raw=load(E/f"{key}_rag_documents.json")
  docs += [{"id":x["id"],"title":f"{key} held-out evidence","category":key,"content":x["content"],"metadata":{"persona":key,"held_out":True}}for x in raw]
  for x in ds:
   if x["category"]=="rag_grounded":questions.append({"id":x["id"],"question":x["prompt"],"expected_doc_ids":x["expected_refs"],"gold_answer":x["expected_behavior"],"persona":key})
 O.mkdir(parents=True,exist_ok=True)
 (O/"character_rag_seed_documents.json").write_text(json.dumps({"schema_version":1,"description":"Held-out character RAG evidence; never use for SFT.","documents":docs},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 (O/"character_rag_retrieval_eval.json").write_text(json.dumps({"schema_version":1,"questions":questions},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 print({"documents":len(docs),"questions":len(questions)})
if __name__=="__main__":main()
