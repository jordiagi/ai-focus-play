import sys, glob, json
sys.path.insert(0, "/opt/PnLCalib")
import cv2, yaml, torch, numpy as np
import torchvision.transforms as T
from model.cls_hrnet import get_cls_net
from model.cls_hrnet_l import get_cls_net as get_cls_net_l
from utils.utils_calib import FramebyFrameCalib
from utils.utils_heatmap import (get_keypoints_from_heatmap_batch_maxpool,
                                 get_keypoints_from_heatmap_batch_maxpool_l,
                                 complete_keypoints, coords_to_dict)
dev="cuda:0"
cfg=yaml.safe_load(open("/opt/PnLCalib/config/hrnetv2_w48.yaml"))
cfgl=yaml.safe_load(open("/opt/PnLCalib/config/hrnetv2_w48_l.yaml"))
m=get_cls_net(cfg);  m.load_state_dict(torch.load("/opt/PnLCalib/weights/SV_kp",map_location=dev)); m.to(dev).eval()
ml=get_cls_net_l(cfgl); ml.load_state_dict(torch.load("/opt/PnLCalib/weights/SV_lines",map_location=dev)); ml.to(dev).eval()
tr=T.Resize((540,960))
frames=sorted(glob.glob("/workspace/aifp/frames/reg/*.jpg"))
print(f"frames: {len(frames)}")
for kpt,lnt in [(0.3434,0.7867),(0.20,0.50),(0.15,0.30),(0.10,0.20)]:
    ok=0; kps=[]; lns=[]
    for p in frames:
        fr=cv2.imread(p); h,w=fr.shape[:2]
        cam=FramebyFrameCalib(iwidth=w,iheight=h,denormalize=True)
        img=tr(T.functional.to_tensor(cv2.cvtColor(fr,cv2.COLOR_BGR2RGB)).float())
        with torch.no_grad():
            hm=m(img.unsqueeze(0).to(dev)); hml=ml(img.unsqueeze(0).to(dev))
        kpd=coords_to_dict(get_keypoints_from_heatmap_batch_maxpool(hm[:,:-1,:,:]),threshold=kpt)
        lnd=coords_to_dict(get_keypoints_from_heatmap_batch_maxpool_l(hml[:,:-1,:,:]),threshold=lnt)
        k2,l2=complete_keypoints(kpd[0],lnd[0],w=w,h=h,normalize=True)
        cam.update(k2,l2)
        fp=cam.heuristic_voting(refine_lines=True)
        kps.append(len(kpd[0])); lns.append(len(lnd[0]))
        if fp is not None: ok+=1
    kps=sorted(kps); lns=sorted(lns)
    print(f"  kp_thr={kpt:<6} line_thr={lnt:<5}  calibrated {ok}/{len(frames)} = {ok/len(frames):.2f}   "
          f"median kp={kps[len(kps)//2]:>3}  median lines={lns[len(lns)//2]:>3}")
