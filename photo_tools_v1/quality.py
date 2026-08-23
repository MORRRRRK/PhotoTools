"""quality.py - 照片/视频质量评估引擎 (V1.0)"""

import os, math
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import List, Optional
import numpy as np
from PIL import Image

cv2 = None
def _import_cv2():
    global cv2
    if cv2 is None:
        try:
            import cv2 as _cv2; cv2 = _cv2
        except ImportError:
            pass

def _clamp(v):
    return max(0.0, min(100.0, v))
def _gray(rgb):
    return np.mean(rgb, axis=2).astype(np.uint8)

@dataclass
class PhotoScore:
    file: str = ""
    filename: str = ""
    width: int = 0; height: int = 0
    total_score: float = 0.0
    composition: float = 0.0; exposure: float = 0.0
    sharpness: float = 0.0; color_score: float = 0.0; noise_score: float = 0.0
    sharpness_value: float = 0.0; brightness_mean: float = 0.0
    contrast: float = 0.0; colorfulness: float = 0.0
    shadow_clip_pct: float = 0.0; highlight_clip_pct: float = 0.0
    recommendation: str = ""
    def to_dict(self):
        return {k: round(v,1) if isinstance(v,float) else v for k,v in self.__dict__.items()}

@dataclass
class VideoScore:
    file: str = ""; filename: str = ""
    duration_sec: float = 0.0; frame_count: int = 0
    avg_score: float = 0.0; min_score: float = 0.0; max_score: float = 0.0
    frame_scores: List[PhotoScore] = field(default_factory=list)
    recommendation: str = ""

def load_image(path):
    try:
        img = Image.open(path)
        try:
            from PIL import ImageOps
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass
        return np.array(img.convert("RGB"))
    except Exception:
        return None

def _convolve2d(img, kernel):
    h,w = img.shape; kh,kw = kernel.shape
    ph,pw = kh//2, kw//2
    pad = np.pad(img, ((ph,ph),(pw,pw)), mode="edge")
    out = np.zeros_like(img)
    for i in range(h):
        for j in range(w):
            out[i,j] = np.sum(pad[i:i+kh, j:j+kw]*kernel)
    return out

def evaluate_sharpness(img):
    _import_cv2()
    gray = _gray(img)
    if cv2:
        lap = cv2.Laplacian(gray, cv2.CV_64F)
        lap_var = float(lap.var())
    else:
        k = np.array([[0,1,0],[1,-4,1],[0,1,0]], dtype=np.float64)
        lap_var = float(np.var(_convolve2d(gray.astype(np.float64), k)))
    return _clamp((lap_var/1000)*100), lap_var

def evaluate_exposure(img):
    gray = _gray(img)
    hist,_ = np.histogram(gray, bins=256, range=(0,256))
    total = gray.size
    shadow = np.sum(hist[:30])/total*100
    highlight = np.sum(hist[226:])/total*100
    mean_b = float(np.mean(gray))
    contrast = float(np.std(gray))
    bright = max(0, min(100, 100-abs(mean_b-128)/50*100))
    penalty = max(0, shadow-5)*2 + max(0, highlight-5)*2
    bonus = min(20, contrast/10)
    return _clamp(bright-penalty+bonus), mean_b, contrast, shadow, highlight

def evaluate_composition(img):
    _import_cv2()
    h,w,_ = img.shape; gray = _gray(img)
    score = 50.0; tw,th = w/3, h/3
    if cv2:
        gx = cv2.Sobel(gray, cv2.CV_64F, 1,0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_64F, 0,1, ksize=3)
        mag = np.sqrt(gx**2+gy**2)
    else:
        sx = np.array([[-1,0,1],[-2,0,2],[-1,0,1]], dtype=np.float64)
        sy = np.array([[-1,-2,-1],[0,0,0],[1,2,1]], dtype=np.float64)
        mag = np.sqrt(_convolve2d(gray.astype(np.float64),sx)**2+_convolve2d(gray.astype(np.float64),sy)**2)
    mask = np.zeros((h,w), dtype=bool)
    for x in [int(tw), int(2*tw)]:
        m = max(0,x-int(w*0.02)); n = min(w,x+int(w*0.02)); mask[:,m:n] = True
    for y in [int(th), int(2*th)]:
        m = max(0,y-int(h*0.02)); n = min(h,y+int(h*0.02)); mask[m:n,:] = True
    if np.sum(mag) > 0:
        r = np.sum(mag[mask])/np.sum(mag)
        if 0.15 < r < 0.5: score += 20
    mid = w//2
    left = gray[:,:mid].astype(float)
    right = gray[:,mid:mid+left.shape[1]].astype(float)
    if left.shape == right.shape:
        if max(0,100-np.mean(np.abs(left-right[:,::-1]))/2.5) > 70: score += 10
    if cv2:
        e = cv2.Canny(gray,50,150)
        er = np.sum(e>0)/(h*w)
        if er < 0.01: score -= 15
        elif er > 0.3: score -= 10
    return _clamp(score)

def evaluate_color(img):
    _import_cv2()
    if cv2:
        hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
        sat = hsv[:,:,1].astype(float)
    else:
        r,g,b = img[:,:,0].astype(float),img[:,:,1].astype(float),img[:,:,2].astype(float)
        sat = np.maximum(np.maximum(r,g),b)-np.minimum(np.minimum(r,g),b)
    m,s = float(np.mean(sat)), float(np.std(sat))
    cf = math.sqrt(m**2+s**2)
    if cf < 10: score = 30
    elif cf < 30: score = 50+(cf-10)*1.5
    elif cf < 80: score = 80
    else: score = max(0,80-(cf-80)*0.2)
    return _clamp(score), cf

def evaluate_noise(img):
    gray = _gray(img).astype(float)
    h,w = gray.shape; vs = []
    for y in range(0,h-8,32):
        for x in range(0,w-8,32):
            b = gray[y:y+8,x:x+8]
            if b.shape[0]>=4 and b.shape[1]>=4: vs.append(float(np.var(b)))
    if not vs: return 50
    vs.sort()
    return _clamp(100-np.mean(vs[:max(1,len(vs)//5)])/200*100)

def evaluate_photo(path):
    img = load_image(path)
    if img is None: return None
    h,w,_ = img.shape
    ss,sv = evaluate_sharpness(img)
    es,br,cnt,sh,hl = evaluate_exposure(img)
    cs = evaluate_composition(img)
    cl,cv = evaluate_color(img)
    ns = evaluate_noise(img)
    total = ss*0.20+es*0.25+cs*0.25+cl*0.15+ns*0.15
    issues = []
    if ss<40: issues.append("清晰度不足")
    if sh>15: issues.append("暗部细节丢失")
    if hl>15: issues.append("高光过曝")
    if cs<40: issues.append("构图需改善")
    if cl<40: issues.append("色彩表现欠佳")
    if ns<40: issues.append("噪点较多")
    rec = "优秀，推荐保留" if total>=80 else ("良好，可保留" if total>=60 else "一般")
    if issues: rec = "；".join(issues)
    return PhotoScore(file=path, filename=os.path.basename(path), width=w, height=h,
        total_score=total, composition=cs, exposure=es, sharpness=ss,
        color_score=cl, noise_score=ns, sharpness_value=sv, brightness_mean=br,
        contrast=cnt, colorfulness=cv, shadow_clip_pct=sh, highlight_clip_pct=hl,
        recommendation=rec)

def evaluate_photos_batch(paths, max_workers=4):
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        fut = {ex.submit(evaluate_photo, p):p for p in paths}
        for f in as_completed(fut):
            try:
                r = f.result()
                if r: results.append(r)
            except: pass
    return results

def evaluate_video(path, sample_interval=2.0):
    _import_cv2()
    if not cv2: return None
    fname = os.path.basename(path)
    cap = cv2.VideoCapture(path)
    if not cap.isOpened(): return None
    try:
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_f = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        dur = total_f/fps if fps>0 and total_f>0 else 0
        step = max(1, int(fps*sample_interval))
        scores = []; idx = 0
        while True:
            ret,frame = cap.read()
            if not ret: break
            if idx%step==0:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h,w = rgb.shape[:2]
                ss,_ = evaluate_sharpness(rgb); es,_,_,_,_ = evaluate_exposure(rgb)
                cs = evaluate_composition(rgb); cl,_ = evaluate_color(rgb); ns = evaluate_noise(rgb)
                t = ss*0.20+es*0.25+cs*0.25+cl*0.15+ns*0.15
                scores.append(PhotoScore(file=path, filename=f"{fname}[{idx}]",
                    width=w,height=h,total_score=t,composition=cs,exposure=es,
                    sharpness=ss,color_score=cl,noise_score=ns))
            idx += 1
        cap.release()
        if not scores: return None
        sv = [s.total_score for s in scores]
        avg = float(np.mean(sv))
        rec = "视频质量较好" if avg>=60 else "视频质量一般"
        return VideoScore(file=path,filename=fname,duration_sec=dur,frame_count=len(scores),
            avg_score=avg,min_score=float(min(sv)),max_score=float(max(sv)),
            frame_scores=scores,recommendation=rec)
    except Exception as e:
        cap.release(); return None
