# 摄影相册网页

静态摄影画廊，深色界面，支持相册筛选、点击放大、键盘翻页，并且做了分批加载，几千张照片也能流畅浏览。

## 目录结构

```
photo_gallery/
├── build_gallery.py    # 照片处理 + 站点生成脚本
├── build_gallery.bat   # Windows 一键重建
├── serve.bat           # 本地预览
└── site/               # 生成结果，部署这个文件夹
    ├── index.html
    ├── styles.css
    ├── app.js
    ├── photos.json
    ├── photos/         # 网页大图 WebP
    └── thumbs/         # 列表缩略图 WebP
```

## 更新照片

1. 把新照片放进 `陈大可照片` 目录，可以按主题建立子文件夹，子文件夹会成为网站上的相册分类。
2. 双击 `photo_gallery\build_gallery.bat`，或在 `photo_gallery` 目录运行：
   ```bash
   python build_gallery.py
   ```
3. 只重新生成变化过的图片；如果想全部重新压缩，加参数：
   ```bash
   python build_gallery.py --force
   ```
4. 生成结果在 `photo_gallery\site`。

原图不会被修改或删除；网页只使用压缩后的 WebP 副本。

## 本地预览

双击 `photo_gallery\serve.bat`，然后访问 `http://127.0.0.1:8000`。

也可以手动运行：

```bash
python -m http.server 8000 -d photo_gallery\site
```

## 部署到 Cloudflare Pages

1. 注册并登录 [Cloudflare](https://dash.cloudflare.com/)。
2. 左侧菜单进入 `Workers & Pages`，点击 `Create`，选择 `Pages`，再选择 `Upload assets`。
3. 项目名称填一个英文名，例如 `chen-dake-photos`。
4. 把 `photo_gallery\site` 文件夹拖进去上传。
5. 部署完成后会得到一个公网地址：`https://chen-dake-photos.pages.dev`。
6. 以后更新照片时，重新运行构建脚本，然后在 Pages 项目里重新上传 `site` 文件夹即可。

## 自定义域名（可选）

在 Pages 项目的 `Custom domains` 里绑定自己的域名即可，需要先把域名接入 Cloudflare 的 DNS。

## 隐私提醒

部署后任何人都可以通过链接访问页面。照片本身建议只放压缩版，原图保留在本地；如果只想让指定的人看，可以后续用 Cloudflare Access 加登录验证。
