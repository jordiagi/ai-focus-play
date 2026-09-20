"""Numeric probe: does PnLCalib actually calibrate OUR footage?
The visualisation showed nothing, which could be a detection failure or a drawing
quirk. This reports the counts and the projection matrix so the answer is unambiguous."""
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

dev = "cuda:0"
cfg  = yaml.safe_load(open("/opt/PnLCalib/config/hrnetv2_w48.yaml"))
cfgl = yaml.safe_load(open("/opt/PnLCalib/config/hrnetv2_w48_l.yaml"))
m  = get_cls_net(cfg);   m.load_state_dict(torch.load("/opt/PnLCalib/weights/SV_kp", map_location=dev)); m.to(dev).eval()
ml = get_cls_net_l(cfgl); ml.load_state_dict(torch.load("/opt/PnLCalib/weights/SV_lines", map_location=dev)); ml.to(dev).eval()
tr = T.Resize((540, 960))

for path in sys.argv[1:]:
    frame = cv2.imread(path)
    h, w = frame.shape[:2]
    cam = FramebyFrameCalib(iwidth=w, iheight=h, denormalize=True)
    img = tr(f_ := T.functional.to_tensor(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).float())
    with torch.no_grad():
        hm  = m(img.unsqueeze(0).to(dev))
        hml = ml(img.unsqueeze(0).to(dev))
    kpc = get_keypoints_from_heatmap_batch_maxpool(hm[:, :-1, :, :])
    lnc = get_keypoints_from_heatmap_batch_maxpool_l(hml[:, :-1, :, :])
    kpd = coords_to_dict(kpc, threshold=0.3434)
    lnd = coords_to_dict(lnc, threshold=0.7867)
    kpd2, lnd2 = complete_keypoints(kpd[0], lnd[0], w=w, h=h, normalize=True)
    cam.update(kpd2, lnd2)
    fp = cam.heuristic_voting(refine_lines=True)
    print(f"\n{path.split('/')[-1]}")
    print(f"  raw keypoints over threshold : {len(kpd[0])}")
    print(f"  raw line points over threshold: {len(lnd[0])}")
    print(f"  after completion  kp={len(kpd2)}  lines={len(lnd2)}")
    print(f"  calibration: {'SUCCESS' if fp is not None else 'FAILED (heuristic_voting returned None)'}")
