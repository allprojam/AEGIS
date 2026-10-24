import urllib.request,json,time,os
CONTRACTS={
 "StabilityPool":"0x37FfD5d66Fb182493C315B8b8f1C9D67DcF95B18",
 "CollateralRegistry":"0x9cbB9b5376F2ecF281ff66BBA8fE2d70f48138F4",
 "ActivePool":"0xfa88E9034b82e396bC40b4D22227b84e2a4546C1",
 "TroveManager":"0xf0C949513ff4ecFf1C0afC7c1966dCb8DfAC950b",
 "EnosysLoansFXRP":"0x5734E64d12621d353772D05210675B17923F3ff6",
 "BorrowerOperations":"0x59a4c88A98F3b515aE041005206E74D0ddFb6cB1",
}
for name,addr in CONTRACTS.items():
    for att in range(4):
        try:
            u=f"https://flare-explorer.flare.network/api/v2/smart-contracts/{addr}"
            r=urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
            j=json.loads(urllib.request.urlopen(r,timeout=30).read().decode())
            abi=j.get("abi") or []
            json.dump(abi,open(f"enosys/abi/{name}.json","w"),indent=1)
            fns=sorted({a["name"] for a in abi if a.get("type")=="function"})
            print(f"\n{name} {addr}  ({len(abi)} abi entries, {len(fns)} functions)",flush=True)
            print("   ", ", ".join(fns[:40]),flush=True)
            break
        except Exception as e:
            print(f"  {name} att{att} {str(e)[:40]}",flush=True); time.sleep(10)
    time.sleep(3)
