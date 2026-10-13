"""Bandingkan data di laptopmu dengan data acuan panduan; hanya yang BEDA yang dicetak.

Jalankan dari folder utama project:  python cek_beda.py
"""
import csv, hashlib, json
from pathlib import Path

def h(s): return hashlib.md5(s.encode("utf-8")).hexdigest()[:10]

def hitung(root="."):
    root = Path(root); out = {"clean": {}, "metadata": {}, "chunks": {}, "questions": {}}
    for f in sorted((root / "data/clean").glob("*.json")):
        rec = json.loads(f.read_text(encoding="utf-8"))
        out["clean"][str(rec["no_urut"])] = h(rec["teks"])
    with open(root / "data/metadata.csv", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            out["metadata"][row["no_urut"]] = h(json.dumps(row, sort_keys=True, ensure_ascii=False))
    per = {}
    for baris in open(root / "data/chunks.jsonl", encoding="utf-8"):
        c = json.loads(baris)
        per.setdefault(str(c["no_urut"]), []).append(json.dumps(c, sort_keys=True, ensure_ascii=False))
    out["chunks"] = {k: h("\n".join(v)) for k, v in per.items()}
    for baris in open(root / "eval/questions.jsonl", encoding="utf-8"):
        q = json.loads(baris)
        out["questions"][q["id"]] = h(json.dumps(q, sort_keys=True, ensure_ascii=False))
    return out


ACUAN = {"clean":{"105":"1cf94496a0","159":"3aa4a50dbb","188":"328fac705e","222":"a99417ddf1","235":"b8d2e62830","268":"f079e5451b","269":"13925045bd","307":"243378d13e","308":"f78270021c","310":"81661aee27","311":"2401104cc0","313":"a5dfe6d9b6","320":"0881cb99e3","324":"d9233521e5","325":"cc1a36185d","326":"5dafab9409","327":"74af66d1df","347":"a7f78f2606","348":"d296058898","363":"4697010bdb","364":"75dc6d2bdd","370":"90d808a46c","371":"1e9db84d62","372":"2d6412e5a1","387":"b83c80aed2","388":"8c33247aa3","390":"18724c9c1e","391":"3a824fdb95","394":"1011f2b811","406":"c31fa0cd09","407":"ffc12276c4","409":"7ea6913fa4","417":"81cad14959","418":"22590074bc","419":"56f04c609b","424":"0b514797e0","429":"7af3a7edf4","430":"176d21c71d","441":"4beb29b009","445":"b7fe5d033b","446":"393eb21e0f","452":"089a0d0731","464":"0a62563b56","499":"9ab7081101","509":"4a58252000","511":"e21c925609","529":"d88241b077","531":"d4c2d60dc3","561":"fdfe9c0138","562":"6055f9c7b9","629":"ace1a52f98"},"metadata":{"105":"c5690b7b41","159":"467a7d7fe5","188":"1d1d570d43","222":"d98ef705ea","235":"87af832dd2","268":"3727910838","269":"5e4e22e2d4","307":"45df2edf8c","308":"5bf59792d6","310":"e96c69f178","311":"2675adf592","313":"b0353691f1","320":"99d52fcd06","324":"20e84f3de4","325":"dcb75c5a8b","326":"3703d7e76d","327":"96cbe33f64","347":"9d1bb41a45","348":"efc3110ae2","363":"7ff3a4fb65","364":"5cda542b59","370":"9c2d484c9e","371":"9b2a8dfe47","372":"f382858901","387":"aff6168a5c","388":"9c9caa0d42","390":"3f4b52fd75","391":"2ca5c8bd0c","394":"c8bdc17bb6","406":"0922cc0a07","407":"194f79e4a2","409":"9a1cbf64ea","417":"0cea7e81f7","418":"6d9aa940ba","419":"15e58d5660","424":"3e38b4383f","429":"94ca0d8511","430":"9365cd6a5a","441":"dd38c58083","445":"5e948fd18d","446":"1eb4c7c185","452":"f70ce35ecb","464":"df3d63fc68","499":"7426b9e956","509":"21bdfe4bf2","511":"467392655b","529":"c6635214eb","531":"a5a5924feb","561":"bd3cc6a7f3","562":"1f389ebf00","629":"c6b0472ded"},"chunks":{"105":"8dcc39402d","159":"8bbd4bda85","188":"17dda89b5f","222":"216b1f0e99","235":"fe76f8383f","268":"6ba5853879","269":"ac7351f858","307":"5e7cf0111b","308":"2d13996538","310":"51a529d411","311":"a6f55c8a49","313":"ce2ac3b02e","320":"994d9e072c","324":"6ebb8ff200","325":"ec9cb2340b","326":"761d1a7fb0","327":"36c1249f43","347":"5c048358b5","348":"457bb6aa4a","363":"2e012d9ad4","364":"fd8b29a0bb","370":"49c0dfef82","371":"4164e5fa1d","372":"5379b20922","387":"082fc7137a","388":"1cf9160d1b","390":"ae8c4d3ceb","391":"7c43f74c9b","394":"8c0c7c0147","406":"061921cddf","407":"e26d75dee3","409":"a20c94a3ee","417":"3007ce6ae6","418":"7918ffc16b","419":"84398233f3","424":"84c6b3a068","429":"0f0b6bbfbd","430":"593fd07b33","441":"76b509cc7d","445":"a38050baed","446":"3801b62a87","452":"5934f7299c","464":"1fed4c5576","499":"ceda909941","509":"9047431ecf","511":"dc8cfedf61","529":"66326e8af3","531":"67dde00dca","561":"7ce0c6f9e4","562":"3da8fdabd6","629":"00c4cdac2d"},"questions":{"Q01":"7b6855e6bb","Q02":"ff0fbeed5c","Q03":"24ce1c5261","Q04":"62efab5f13","Q05":"edac4587a6","Q06":"1e94255e8c","Q07":"af40d60a98","Q08":"c7808ae10c","Q09":"4cbb4ac40d","Q10":"4e395795d0","Q11":"11740290d3","Q12":"445ce08d4f","Q13":"190f915109","Q14":"f37c11f134","Q15":"c9ad03f74d","Q16":"afc142ced0","Q17":"d1d02cc95f","Q18":"46fccc8c0a","Q19":"951dcbb2c5","Q20":"3357ed6e1b","Q21":"db8396db44","Q22":"b253c9c36e","Q23":"d9b667eab3","Q24":"f374729add","Q25":"2b798954e2","A026":"f60caf8d4e","A027":"fcaaa1baf6","A028":"5393ea7474","A029":"e30e82a54c","A030":"f5a76bfeb2","A031":"90f07b214a","A032":"ae2448aea0","A033":"c11ac7576b","A034":"90ef642781","A035":"10ea3910bc","A036":"628d822324","A037":"226f06c70a","A038":"074dd1d7d9","A039":"744084fc36","A040":"b976d31090","A041":"cbe1f42f7f","A042":"9d2a93a777","A043":"220cda5620","A044":"51537ba543","A045":"b84eca0c97","A046":"87590de5b7","A047":"9fcb46ad3e","A048":"5e7d69d888","A049":"900258c961","A050":"c33fb56c9d","A051":"dc567bb8a4","A052":"5677b78163","A053":"0d1000fd99","A054":"55cd8165c9","A055":"b8add8fc40","A056":"e6bb6a6e42","A057":"34d545f962","A058":"41763546aa","A059":"33de52593c","A060":"5d75bc0898","A061":"e136886250","A062":"294b0bc182","A063":"519d48f639","A064":"9e73568a98","A065":"15e966efb5","A066":"44f9dcf992","A067":"1a9dc0d76a","A068":"d3b2e21082","A069":"6df54b88c9","A070":"44404adbe8","A071":"f90e3b5d7f","A072":"4c96573115","A073":"c919b59207","A074":"29a3254608","A075":"06a3ac8d63","A076":"e5f7bb9756","A077":"6311beb69f","A078":"f545e3c0e8","A079":"9b6c33c84f","A080":"d7e2a653e9","A081":"dbfbe5bf97","A082":"fed73ea266"}}


if __name__ == "__main__":
    punyaku = hitung(".")
    for bagian in ["clean", "metadata", "chunks", "questions"]:
        beda = [k for k in ACUAN[bagian] if punyaku[bagian].get(k) != ACUAN[bagian][k]]
        lebih = [k for k in punyaku[bagian] if k not in ACUAN[bagian]]
        print(f"{bagian:<10} beda: {beda if beda else 'tidak ada'}" + (f" | tambahan: {lebih}" if lebih else ""))