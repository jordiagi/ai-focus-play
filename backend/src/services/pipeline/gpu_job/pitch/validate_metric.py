"""END-TO-END metric validation: how many METRES is our pitch position wrong by?

Line-alignment is a proxy. This is the real thing, and it is the L2 gate:
  frame at a Veo event time -> PnLCalib camera -> detect ball -> image->pitch metres
  -> compare against Veo's own (x,z) for that event.

Only frames whose calibration is independently well-aligned are used, because a bad
calibration's metric error is meaningless noise.

Known slop in the reference, stated so the number is read correctly: at a throw-in the
ball is often in the thrower's hands 1-2 m infield, Veo's own coordinates carry a ~2 m
bias, and for a tackle/interception Veo marks the ACTION not a detectable ball. So
restarts are reported separately from open-play events.
"""
import sys, csv, json, glob
sys.path.insert(0,"/opt/PnLCalib")
import cv2, yaml, torch, numpy as np
import torchvision.transforms as T
from model.cls_hrnet import get_cls_net
from model.cls_hrnet_l import get_cls_net as get_cls_net_l
from utils.utils_calib import FramebyFrameCalib
from utils.utils_heatmap import (get_keypoints_from_heatmap_batch_maxpool,
                                 get_keypoints_from_heatmap_batch_maxpool_l,
                                 complete_keypoints, coords_to_dict)
from inference import lines_coords, projection_from_cam_params
from ultralytics import YOLO

dev="cuda:0"
torch.cuda.set_per_process_memory_fraction(0.30, 0)
cfg=yaml.safe_load(open("/opt/PnLCalib/config/hrnetv2_w48.yaml"))
cfgl=yaml.safe_load(open("/opt/PnLCalib/config/hrnetv2_w48_l.yaml"))
m=get_cls_net(cfg);  m.load_state_dict(torch.load("/opt/PnLCalib/weights/SV_kp",map_location=dev)); m.to(dev).eval()
ml=get_cls_net_l(cfgl); ml.load_state_dict(torch.load("/opt/PnLCalib/weights/SV_lines",map_location=dev)); ml.to(dev).eval()
tr=T.Resize((540,960))
yolo=YOLO("yolo11x.pt"); BALL=32
RESTART={"FootballKickOff","FootballCornerKick","FootballThrowIn","FootballGoalKick"}

def white_mask(b):
    h=cv2.cvtColor(b,cv2.COLOR_BGR2HSV)
    return cv2.dilate(((h[:,:,2]>170)&(h[:,:,1]<70)).astype(np.uint8)*255,np.ones((7,7),np.uint8),1)

def calib(fr):
    h,w=fr.shape[:2]
    cam=FramebyFrameCalib(iwidth=w,iheight=h,denormalize=True)
    img=tr(T.functional.to_tensor(cv2.cvtColor(fr,cv2.COLOR_BGR2RGB)).float())
    with torch.no_grad():
        hm=m(img.unsqueeze(0).to(dev)); hml=ml(img.unsqueeze(0).to(dev))
    kpd=coords_to_dict(get_keypoints_from_heatmap_batch_maxpool(hm[:,:-1,:,:]),threshold=0.15)
    lnd=coords_to_dict(get_keypoints_from_heatmap_batch_maxpool_l(hml[:,:-1,:,:]),threshold=0.30)
    k2,l2=complete_keypoints(kpd[0],lnd[0],w=w,h=h,normalize=True)
    cam.update(k2,l2); fp=cam.heuristic_voting(refine_lines=True)
    return (projection_from_cam_params(fp) if fp is not None else None)

def align(fr,P):
    mask=white_mask(fr); h,w=fr.shape[:2]; on=tot=0
    for a,b in lines_coords:
        for t in np.linspace(0,1,40):
            X=np.array([a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t,a[2]+(b[2]-a[2])*t,1.0])
            q=P@X
            if abs(q[2])<1e-6: continue
            x,y=int(q[0]/q[2]),int(q[1]/q[2])
            if 0<=x<w and 0<=y<h:
                tot+=1; on+= 1 if mask[y,x]>0 else 0
    return on/tot if tot else 0.0

def img_to_pitch(P,u,v):
    """Invert the projection onto the ground plane z=0."""
    A=np.array([[P[0,0],P[0,1],P[0,3]-u*P[2,3]],
                [P[1,0],P[1,1],P[1,3]-v*P[2,3]],
                [P[2,0],P[2,1],-1.0]])
    Hg=np.array([[P[0,0],P[0,1],P[0,3]],[P[1,0],P[1,1],P[1,3]],[P[2,0],P[2,1],P[2,3]]])
    try: Hi=np.linalg.inv(Hg)
    except np.linalg.LinAlgError: return None
    q=Hi@np.array([u,v,1.0])
    if abs(q[2])<1e-9: return None
    return q[0]/q[2], q[1]/q[2]

def ball_px(fr):
    h,w=fr.shape[:2]; best=None; bc=0
    top=int(h*0.22); th=(h-top)//2; tw=w//3
    for iy in range(2):
        for ix in range(3):
            x0,y0=max(0,ix*tw-100),max(top,top+iy*th-60)
            x1,y1=min(w,(ix+1)*tw+100),min(h,top+(iy+1)*th+60)
            r=yolo.predict(fr[y0:y1,x0:x1],imgsz=640,conf=0.05,classes=[BALL],device=dev,half=True,verbose=False)[0]
            if r.boxes is None or len(r.boxes)==0: continue
            cf=r.boxes.conf.cpu().numpy(); xy=r.boxes.xywh.cpu().numpy(); k=int(cf.argmax())
            if float(cf[k])>bc: bc=float(cf[k]); best=(x0+float(xy[k][0]),y0+float(xy[k][1]))
    return best,bc

rows=[r for r in csv.DictReader(open("/workspace/aifp/code/benchmarks/raw/veo_events_447.csv")) if r["x"] and r["z"]]
res={"restart":[], "open":[]}
stats={"tried":0,"calibrated":0,"aligned":0,"ball":0,"scored":0}
for r in rows:
    vt=int(r["video_time_ms"])/1000.0
    p=f"/workspace/aifp/frames/calib/ev_{int(vt*1000):08d}.jpg"
    fr=cv2.imread(p)
    if fr is None: continue
    stats["tried"]+=1
    P=calib(fr)
    if P is None: continue
    stats["calibrated"]+=1
    if align(fr,P)<0.5: continue
    stats["aligned"]+=1
    b,_=ball_px(fr)
    if b is None: continue
    stats["ball"]+=1
    pm=img_to_pitch(P,b[0],b[1])
    if pm is None: continue
    gx,gz=float(r["x"])*105.0, float(r["z"])*68.0
    e=float(np.hypot(pm[0]-gx, pm[1]-gz))
    res["restart" if r["event_type"] in RESTART else "open"].append(e)
    stats["scored"]+=1

print(json.dumps(stats))
for k,v in res.items():
    if not v: print(f"  {k}: no samples"); continue
    v=sorted(v)
    print(f"  {k:8} n={len(v):>3}  median={v[len(v)//2]:6.2f} m  p90={v[int(0.9*len(v))-1] if len(v)>=10 else float('nan'):6.2f} m  min={v[0]:5.2f}  max={v[-1]:7.2f}")
