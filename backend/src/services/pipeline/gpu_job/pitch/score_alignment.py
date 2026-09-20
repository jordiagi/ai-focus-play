"""Does a calibration actually LAND on the pitch? Coverage is not accuracy.

Projects the known 105x68 pitch line model into the image using the estimated camera,
then scores how much of the projected line falls on an actual white line pixel. This is
self-contained: it needs no ball detection and no Veo coordinates, so it cannot be fooled
by the same noise that broke the SIFT attempts.

white-line mask = bright AND low-saturation (the blue lines of the other field layout are
saturated, so they are excluded by construction).
"""
import sys, glob
sys.path.insert(0,"/opt/PnLCalib")
import cv2, yaml, torch, numpy as np
import torchvision.transforms as T
from model.cls_hrnet import get_cls_net
from model.cls_hrnet_l import get_cls_net as get_cls_net_l
from utils.utils_calib import FramebyFrameCalib
from utils.utils_heatmap import (get_keypoints_from_heatmap_batch_maxpool,
                                 get_keypoints_from_heatmap_batch_maxpool_l,
                                 complete_keypoints, coords_to_dict)
sys.path.insert(0,"/opt/PnLCalib")
from inference import lines_coords, projection_from_cam_params

dev="cuda:0"
cfg=yaml.safe_load(open("/opt/PnLCalib/config/hrnetv2_w48.yaml"))
cfgl=yaml.safe_load(open("/opt/PnLCalib/config/hrnetv2_w48_l.yaml"))
m=get_cls_net(cfg);  m.load_state_dict(torch.load("/opt/PnLCalib/weights/SV_kp",map_location=dev)); m.to(dev).eval()
ml=get_cls_net_l(cfgl); ml.load_state_dict(torch.load("/opt/PnLCalib/weights/SV_lines",map_location=dev)); ml.to(dev).eval()
tr=T.Resize((540,960))

def white_mask(bgr):
    hsv=cv2.cvtColor(bgr,cv2.COLOR_BGR2HSV)
    # bright + desaturated = white paint; the other field's lines are BLUE (saturated)
    mk=((hsv[:,:,2]>170)&(hsv[:,:,1]<70)).astype(np.uint8)*255
    return cv2.dilate(mk,np.ones((7,7),np.uint8),1)

def score(path,kpt,lnt):
    fr=cv2.imread(path); h,w=fr.shape[:2]
    cam=FramebyFrameCalib(iwidth=w,iheight=h,denormalize=True)
    img=tr(T.functional.to_tensor(cv2.cvtColor(fr,cv2.COLOR_BGR2RGB)).float())
    with torch.no_grad():
        hm=m(img.unsqueeze(0).to(dev)); hml=ml(img.unsqueeze(0).to(dev))
    kpd=coords_to_dict(get_keypoints_from_heatmap_batch_maxpool(hm[:,:-1,:,:]),threshold=kpt)
    lnd=coords_to_dict(get_keypoints_from_heatmap_batch_maxpool_l(hml[:,:-1,:,:]),threshold=lnt)
    k2,l2=complete_keypoints(kpd[0],lnd[0],w=w,h=h,normalize=True)
    cam.update(k2,l2); fp=cam.heuristic_voting(refine_lines=True)
    if fp is None: return None
    P=projection_from_cam_params(fp)
    mask=white_mask(fr)
    on=tot=0
    for a,b in lines_coords:
        for t in np.linspace(0,1,40):
            X=np.array([a[0]+(b[0]-a[0])*t, a[1]+(b[1]-a[1])*t, a[2]+(b[2]-a[2])*t, 1.0])
            q=P@X
            if abs(q[2])<1e-6: continue
            x,y=int(q[0]/q[2]),int(q[1]/q[2])
            if 0<=x<w and 0<=y<h:
                tot+=1; on+= 1 if mask[y,x]>0 else 0
    return (on/tot if tot else 0.0), tot

frames=sorted(glob.glob("/workspace/aifp/frames/reg/*.jpg"))
for kpt,lnt in [(0.3434,0.7867),(0.15,0.30),(0.10,0.20)]:
    res=[score(p,kpt,lnt) for p in frames]
    ok=[r for r in res if r]
    good=[r for r in ok if r[0]>=0.5]
    al=sorted(r[0] for r in ok)
    print(f"  kp={kpt:<6} line={lnt:<5} calibrated {len(ok):>2}/{len(frames)}  "
          f"median line-alignment={al[len(al)//2]:.2f}  "
          f">=0.50 aligned: {len(good):>2}  ({len(good)/len(frames):.2f} of all frames)")
