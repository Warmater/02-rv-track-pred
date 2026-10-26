from pathlib import Path
from html import escape
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent
W,H,S = 1800,2280,2
im=Image.new('RGB',(W*S,H*S),'white'); d=ImageDraw.Draw(im)
svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">', '<title>雷达–视觉融合目标跟踪与轨迹预测 项目技术路线图</title>', '<desc>规划路线：多源输入经过时空对齐、融合检测、跟踪状态估计与多模态预测；长尾场景挖掘形成反馈，统一评测验证改进。</desc>', '<rect width="1800" height="2280" fill="white"/>']
ink='#182C45'; muted='#54657A'; blue='#2464A1'; teal='#187D7C'; orange='#A86928'; line='#AAB8C7'
fonts={}
def font(size,bold=False):
    k=(size,bold)
    if k not in fonts: fonts[k]=ImageFont.truetype('C:/Windows/Fonts/msyhbd.ttc' if bold else 'C:/Windows/Fonts/msyh.ttc',int(size*S))
    return fonts[k]
def text(x,y,t,size=24,color=ink,bold=False,anchor='left'):
    f=font(size,bold); width=d.textlength(t,font=f)/S
    xx=x-width/2 if anchor=='center' else x
    d.text((xx*S,y*S),t,font=f,fill=color,anchor='lt')
    svg.append(f'<text x="{x}" y="{y+size*.88}" fill="{color}" font-family="Microsoft YaHei, Noto Sans CJK SC, sans-serif" font-size="{size}" font-weight="{700 if bold else 400}" text-anchor="{"middle" if anchor=="center" else "start"}">{escape(t)}</text>')
    assert xx>=0 and xx+width<W, (t,xx,width)
def box(x,y,w,h,fill='#FFFFFF',stroke=line,r=12):
    d.rounded_rectangle((x*S,y*S,(x+w)*S,(y+h)*S),radius=r*S,fill=fill,outline=stroke,width=2*S)
    svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
def seg(x1,y1,x2,y2,color=line,width=2,dash=False):
    if dash:
        import math
        length=math.hypot(x2-x1,y2-y1)
        for pos in range(0,int(length),15):
            end=min(pos+8,length)
            d.line(((x1+(x2-x1)*pos/length)*S,(y1+(y2-y1)*pos/length)*S,(x1+(x2-x1)*end/length)*S,(y1+(y2-y1)*end/length)*S),fill=color,width=width*S)
    else: d.line((x1*S,y1*S,x2*S,y2*S),fill=color,width=width*S)
    svg.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{width}"'+(' stroke-dasharray="8 7"' if dash else '')+'/>')
def arrow(x1,y1,x2,y2,color=blue,dash=False):
    import math
    seg(x1,y1,x2,y2,color,3,dash)
    a=math.atan2(y2-y1,x2-x1); points=[(x2,y2),(x2-12*math.cos(a-.45),y2-12*math.sin(a-.45)),(x2-12*math.cos(a+.45),y2-12*math.sin(a+.45))]
    d.polygon([(x*S,y*S) for x,y in points],fill=color)
    svg.append('<polygon points="'+' '.join(f'{x},{y}' for x,y in points)+f'" fill="{color}"/>')
def label(y,n,title,color=blue):
    text(80,y,n,24,color,True); text(128,y-2,title,29,ink,True)

# Each card follows the same reading order: question, input, steps, output, research.
def within(x, y, value, size=24, color=ink, bold=False, width=470):
    assert d.textlength(value, font=font(size,bold))/S <= width, value
    text(x,y,value,size,color,bold)

text(80,48,'雷达–视觉融合目标跟踪与轨迹预测',44,ink,True)
text(80,114,'技术路线详解  /  沿实线读主流程：输入 → 编号步骤 → 输出；虚线表示实验反馈',25,muted)
box(80,166,1640,82,'#EDF4FA','#C5D7E8')
text(106,188,'研究目标',26,blue,True)
text(260,188,'找到目标 → 持续认出同一目标 → 估计运动 → 预测未来 1–3 秒的可能轨迹',26)
label(278,'01','准备数据：先确认各传感器记录了什么')
for x,title,body,sub in [
    (80,'4D 成像毫米波雷达','距离、方位、俯仰、径向速度','RCS：雷达散射截面，描述散射能力'),
    (640,'相机图像','目标外观、类别和场景线索','结合成像几何估计空间位置'),
    (1200,'时间、标定与自车位姿','时间戳、传感器坐标关系','自车位姿：车辆的位置与朝向')]:
    box(x,330,520,120,'#F8FAFC')
    within(x+24,347,title,27,ink,True)
    within(x+24,389,body,23)
    within(x+24,421,sub,22,muted)
for cx in [340,900,1460]: seg(cx,450,cx,477,blue,2)
seg(340,477,1460,477,blue,2)
arrow(340,477,340,546)
text(520,488,'另备参考标注：用于训练与评分；未来真值不进入预测输入。',23,muted)
text(520,522,'先固定训练 / 验证 / 测试划分，并核实连续 ID 与未来标注长度。',22,muted)

cards=[
    (80,'02','时空对齐与融合感知',blue,'#EDF4FA',
     '回答：目标是什么？现在在哪里？',
     '输入：雷达点、图像、时间与标定',
     [('① 时空对齐：让观测对应起来','统一时刻与坐标；补偿自车运动。'),
      ('② 雷达编码：提取空间与运动线索','利用点的位置、径向速度和 RCS。'),
      ('③ 视觉编码：提取外观与深度线索','从图像提取特征，并估计深度。'),
      ('④ 融合检测：共同判断目标位置','BEV＝鸟瞰视角；在统一空间融合。')],
     ['三维目标框、类别、检测分数；','按设计附带融合特征与观测质量。'],
     ['• 先做：标定检查与纯视觉 / 融合对照。',
      '• 后续：外参漂移修正、稀疏点增强。',
      '• 后续：深度不确定性与跨帧融合。']),
    (640,'03','多目标跟踪与状态估计',blue,'#EDF4FA',
     '回答：还是它吗？它正在怎样运动？',
     '输入：当前检测 + 上一帧轨迹状态',
     [('① 运动预测：估计本帧应出现在哪','用上一帧位置、速度外推当前状态。'),
      ('② 数据关联：把检测接到已有轨迹','按位置等线索匹配，排除不合理配对。'),
      ('③ 滤波更新：结合预测与本帧观测','修正位置、速度，记录估计误差范围。'),
      ('④ 身份维护：处理出现、遮挡和离开','保留短时丢失轨迹；重现后尝试接续。')],
     ['目标 ID、历史位置与速度；','状态协方差：描述估计的不确定性。'],
     ['• 先做：卡尔曼滤波 + 显式数据关联。',
      '• 后续：径向速度约束、遮挡恢复。',
      '• 后续：时序查询与检测跟踪联合。']),
    (1200,'04','多模态轨迹预测',teal,'#EDF7F5',
     '回答：未来可能往哪里走？',
     '输入：历史状态 + 可用道路信息',
     [('① 建立基线：先做简单运动外推','匀速 / 匀加速预测，作为比较起点。'),
      ('② 编码上下文：理解运动与周围环境','结合历史、其他目标和可用道路几何。'),
      ('③ 生成候选：给出多种合理未来','预测未来 1–3 秒；为各条轨迹赋概率。'),
      ('④ 检查可行性：是否符合运动规律','检查速度、加速度等是否合理。')],
     ['K 条候选轨迹及对应模式概率；','多模态＝多种未来，例如直行 / 转弯。'],
     ['• 先做：固定时长、采样间隔与候选数。',
      '• 后续：交互建模与多模态预测。',
      '• 后续：上游不确定性传播与概率校准。'])]
for x,n,title,c,bg,question,inputs,steps,outputs,research in cards:
    box(x,555,520,870,'#FFFFFF',c)
    box(x+1,556,518,90,bg,bg,10)
    text(x+22,572,n,26,c,True)
    within(x+76,569,title,28,ink,True,width=426)
    within(x+24,611,question,23,c)
    within(x+24,674,inputs,23,muted)
    seg(x+24,718,x+496,718,'#D8E1EA',1)
    for i,(head,body) in enumerate(steps):
        yy=747+i*90
        within(x+24,yy,head,23,ink,True)
        within(x+24,yy+35,body,22,muted)
    box(x+17,1125,486,116,bg,bg,8)
    text(x+30,1140,'最终预测输出' if n=='04' else '输出给下一环节',23,c,True)
    for i,body in enumerate(outputs): within(x+30,1175+i*30,body,22,c,width=460)
    text(x+24,1265,'实施层次：先做基线，再验证改进',23,c,True)
    for i,body in enumerate(research): within(x+24,1305+i*34,body,22)
arrow(605,1000,635,1000)
arrow(1165,1000,1195,1000,teal)
text(80,1476,'读图提示：径向速度只是沿视线的速度分量；检测分数、状态协方差与轨迹模式概率不能混用。',23,muted)

# Evaluation is a separate offline branch, not an input to future prediction.
seg(340,1425,340,1450,orange,2,True)
seg(900,1425,900,1450,orange,2,True)
seg(1460,1425,1460,1450,orange,2,True)
seg(340,1450,1650,1450,orange,2,True)
arrow(1650,1450,1650,1578,orange,True)
label(1535,'05','长尾与鲁棒性：找出失败条件，再针对性改进',orange)
box(80,1585,1640,205,'#FBF7F0','#D7BE9B')
for x,head,lines in [
    (105,'① 找难例：哪些情况下会失败？',[
        '检查夜间、雨雾、逆光、遮挡与切入。',
        '结合误差、模态不一致与轨迹异常，',
        '整理少见但重要的失败片段。']),
    (655,'② 做实验：问题来自哪个环节？',[
        '分别模拟缺失模态、稀疏雷达回波，',
        '或加入标定扰动，观察性能变化。',
        '真实天气与人为扰动分开报告。']),
    (1205,'③ 再改进：补数据或改模型',[
        '用训练 / 验证难例指导数据补充。',
        '后续研究未知类别识别与保守跟踪。',
        '固定测试集，不让测试样本回流训练。'])]:
    within(x,1605,head,25,orange,True,width=495)
    for i,value in enumerate(lines): within(x,1655+i*37,value,23,width=495)
arrow(900,1790,900,1860,blue)
label(1818,'06','统一评测：结果更准了吗？改善来自哪里？')
box(80,1868,1640,180,'#F7F9FC','#CBD5E1')
for x,title,lines in [
    (105,'检测与跟踪',[
        'mAP：检测准确性；同时关注漏检。',
        'AMOTA：综合跟踪表现。',
        'ID 切换：是否把同一目标认错。']),
    (655,'轨迹与概率质量',[
        'minADE / minFDE：最佳候选轨迹的',
        '平均 / 终点误差；固定候选数与时长。',
        '概率校准：把握程度是否符合实际。']),
    (1205,'对照与消融',[
        '纯视觉 vs 雷达–视觉：融合有用吗？',
        '每次只改一项：收益来自哪个模块？',
        '按场景分组，并报告样本量与波动。'])]:
    within(x,1886,title,26,ink,True,width=495)
    for i,value in enumerate(lines): within(x,1932+i*34,value,23,muted,width=495)
# Feed evaluation findings back to the pipeline through the outer margin.
seg(80,1980,36,1980,orange,2,True)
seg(36,1980,36,1000,orange,2,True)
arrow(36,1000,77,1000,orange,True)
text(80,2070,'虚线反馈：根据评测定位问题，回到相关模块修改并重新比较；所有研究改进均需实验验证。',23,orange)

text(80,2120,'实施顺序',26,ink,True)
stages=[('先对齐数据','投影检查、序列与标注核验'),('再跑通基线','检测 → 跟踪 → 匀速预测'),('逐项增加改进','融合、遮挡、多模态与校准'),('最后联合验证','共享表示、长尾与原型评测')]
for i,(head,sub) in enumerate(stages):
    x=80+i*420
    box(x,2165,380,82,'#FFFFFF','#CAD5E1',8)
    text(x+18,2177,head,25,blue,True)
    within(x+18,2215,sub,21,muted,width=344)
    if i<3: arrow(x+385,2205,x+414,2205)

im.save(OUT/'项目技术路线图.png',dpi=(300,300))
svg.append('</svg>')
(OUT/'项目技术路线图.svg').write_text('\n'.join(svg),encoding='utf-8')
im.resize((1440,1824),Image.Resampling.LANCZOS).save(OUT/'预览.png')
print('Generated PNG (3600 x 4560), editable SVG and preview.')
