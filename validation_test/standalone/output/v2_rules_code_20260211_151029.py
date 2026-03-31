# 竞争区间规则引擎 v2.0 — 挖掘输出
# 生成时间: 2026-02-11 15:10:29
# 数据: 15075 场竞争区间, 训练12060/测试3015

# --- 让方不输规则 ---
@rule('WL-H01', 'H', 'S', 'wl',
      '威廉受让方>4.000 + 立博让方变化>0.049 → OOS 95.8%(n=48)')
def _(m):
    return (m['w_r'] > 4.000 and m['l_hc'] > 0.049)

@rule('T-H02', 'H', 'S', 'wml',
      '立博受让方>3.400 + 威澳返还率差>4.307 → OOS 95.2%(n=62)')
def _(m):
    return (m['l_r'] > 3.400 and m['wm_crr_diff'] > 4.307)

@rule('T-H03', 'H', 'S', 'wml',
      '立博赔率差>1.750 + 威澳返还率差>4.307 → OOS 94.0%(n=50)')
def _(m):
    return (m['l_spread'] > 1.750 and m['wm_crr_diff'] > 4.307)

@rule('D-H04', 'H', 'S', 'wm',
      '澳门受让方>3.150 + 威澳返还率差>4.307 → OOS 93.8%(n=48)')
def _(m):
    return (m['m_r'] > 3.150 and m['wm_crr_diff'] > 4.307)

@rule('T-H05', 'H', 'S', 'wml',
      '澳门赔率差>1.840 + 立博让方变化>0.051 → OOS 93.3%(n=30)')
def _(m):
    return (m['m_spread'] > 1.840 and m['l_hc'] > 0.051)

@rule('WL-H06', 'H', 'S', 'wl',
      '威廉赔率差>2.170 + 立博让方变化>0.049 → OOS 92.7%(n=55)')
def _(m):
    return (m['w_spread'] > 2.170 and m['l_hc'] > 0.049)

@rule('WL-H07', 'H', 'S', 'wl',
      '立博受让方>3.600 + 威廉让方>2.000 → OOS 92.1%(n=38)')
def _(m):
    return (m['l_r'] > 3.600 and m['w_h'] > 2.000)

@rule('D-H08', 'H', 'S', 'wm',
      '澳门赔率差>1.450 + 威澳返还率差>4.307 → OOS 92.1%(n=38)')
def _(m):
    return (m['m_spread'] > 1.450 and m['wm_crr_diff'] > 4.307)

@rule('D-H09', 'H', 'S', 'wm',
      '威廉让方变化<=0.000 + 威廉初盘受让方>4.200 → OOS 92.1%(n=38)')
def _(m):
    return (m['w_hc'] <= 0.000 and m['w_ir'] > 4.200)

@rule('WL-H10', 'H', 'S', 'wl',
      '威廉受让方>4.000 + 立博受让方变化<=-0.093 → OOS 91.9%(n=37)')
def _(m):
    return (m['w_r'] > 4.000 and m['l_rc'] <= -0.093)

@rule('T-H11', 'H', 'S', 'wml',
      '立博让方<=1.800 + 威澳返还率差>4.307 → OOS 91.7%(n=36)')
def _(m):
    return (m['l_h'] <= 1.800 and m['wm_crr_diff'] > 4.307)

@rule('D-H12', 'H', 'S', 'wm',
      '澳门赔率差>1.840 + 威廉让方变化>0.029 → OOS 91.3%(n=46)')
def _(m):
    return (m['m_spread'] > 1.840 and m['w_hc'] > 0.029)

@rule('WL-H13', 'H', 'S', 'wl',
      '立博受让方>3.900 + 立博受让方变化<=-0.054 → OOS 91.2%(n=57)')
def _(m):
    return (m['l_r'] > 3.900 and m['l_rc'] <= -0.054)

@rule('D-H14', 'H', 'S', 'wm',
      '威廉让方<=1.850 + 威廉受让方变化<=-0.133 → OOS 90.9%(n=44)')
def _(m):
    return (m['w_h'] <= 1.850 and m['w_rc'] <= -0.133)

@rule('WL-H15', 'H', 'S', 'wl',
      '立博赔率差>2.100 + 立博让方变化>0.051 → OOS 90.9%(n=44)')
def _(m):
    return (m['l_spread'] > 2.100 and m['l_hc'] > 0.051)

@rule('WL-H16', 'H', 'S', 'wl',
      '威廉受让方>4.000 + 立博平赔变化>0.033 → OOS 90.7%(n=43)')
def _(m):
    return (m['w_r'] > 4.000 and m['l_dc'] > 0.033)

@rule('T-H17', 'H', 'S', 'wml',
      '三公司受让方均值>3.183 + 威澳返还率差>4.307 → OOS 90.5%(n=74)')
def _(m):
    return (m['avg3_r'] > 3.183 and m['wm_crr_diff'] > 4.307)

@rule('WL-H18', 'H', 'S', 'wl',
      '立博受让方>3.900 + 威廉受让方变化<=-0.093 → OOS 90.5%(n=42)')
def _(m):
    return (m['l_r'] > 3.900 and m['w_rc'] <= -0.093)

@rule('D-H19', 'H', 'S', 'wm',
      '澳门初盘受让方>3.650 + 威澳返还率差>3.690 → OOS 90.5%(n=42)')
def _(m):
    return (m['m_ir'] > 3.650 and m['wm_crr_diff'] > 3.690)

@rule('WL-H20', 'H', 'S', 'wl',
      '威廉受让方>4.000 + 立博受让方变化<=-0.054 → OOS 90.4%(n=52)')
def _(m):
    return (m['w_r'] > 4.000 and m['l_rc'] <= -0.054)

@rule('D-H21', 'H', 'S', 'wm',
      '澳门赔率差>1.840 + 威澳返还率差>3.690 → OOS 90.0%(n=50)')
def _(m):
    return (m['m_spread'] > 1.840 and m['wm_crr_diff'] > 3.690)

@rule('D-H22', 'H', 'A', 'wm',
      '澳门让方<=1.900 + 威澳返还率差>4.307 → OOS 89.8%(n=59)')
def _(m):
    return (m['m_h'] <= 1.900 and m['wm_crr_diff'] > 4.307)

@rule('T-H23', 'H', 'A', 'wml',
      '立博让方<=1.800 + 三公司让方变化均值>0.049 → OOS 89.8%(n=49)')
def _(m):
    return (m['l_h'] <= 1.800 and m['avg3_hc'] > 0.049)

@rule('D-H24', 'H', 'A', 'wm',
      '澳门赔率差>1.840 + 威廉让方变化>0.000 → OOS 89.7%(n=68)')
def _(m):
    return (m['m_spread'] > 1.840 and m['w_hc'] > 0.000)

@rule('T-H25', 'H', 'A', 'wml',
      '三公司让方变化均值>0.007 + 澳门赔率差>1.840 → OOS 89.6%(n=67)')
def _(m):
    return (m['avg3_hc'] > 0.007 and m['m_spread'] > 1.840)


# --- 受让不输规则 ---
@rule('WL-R01', 'R', 'A', 'wl',
      '立博受让方变化<=-0.054 + 立博初盘让方>2.400 → OOS 81.2%(n=32)')
def _(m):
    return (m['l_rc'] <= -0.054 and m['l_ih'] > 2.400)

@rule('WL-R02', 'R', 'A', 'wl',
      '立博让方>2.370 + 立博让方变化<=-0.022 → OOS 80.6%(n=36)')
def _(m):
    return (m['l_h'] > 2.370 and m['l_hc'] <= -0.022)

@rule('WL-R03', 'R', 'A', 'wl',
      '威廉让方变化>0.132 + 立博初盘让方>2.400 → OOS 80.6%(n=36)')
def _(m):
    return (m['w_hc'] > 0.132 and m['l_ih'] > 2.400)

@rule('D-R04', 'R', 'A', 'wm',
      '威廉让方变化>0.132 + 威廉初盘返还率>91.420 → OOS 80.6%(n=36)')
def _(m):
    return (m['w_hc'] > 0.132 and m['w_irr'] > 91.420)

@rule('WL-R05', 'R', 'B', 'wl',
      '立博让方变化>0.136 + 立博受让方变化>-0.147 → OOS 77.5%(n=40)')
def _(m):
    return (m['l_hc'] > 0.136 and m['l_rc'] > -0.147)

@rule('D-R06', 'R', 'B', 'wm',
      '澳门让方<=2.400 + 威廉让方>2.500 → OOS 77.1%(n=35)')
def _(m):
    return (m['m_h'] <= 2.400 and m['w_h'] > 2.500)

@rule('WL-R07', 'R', 'B', 'wl',
      '立博让方>2.500 + 立博让方变化>0.129 → OOS 76.8%(n=82)')
def _(m):
    return (m['l_h'] > 2.500 and m['l_hc'] > 0.129)

@rule('WL-R08', 'R', 'B', 'wl',
      '立博让方变化>0.049 + 立博初盘让方>2.400 → OOS 76.7%(n=43)')
def _(m):
    return (m['l_hc'] > 0.049 and m['l_ih'] > 2.400)

@rule('T-R09', 'R', 'B', 'wml',
      '三公司赔率差均值<=0.147 + 澳门让方<=2.400 → OOS 76.6%(n=47)')
def _(m):
    return (m['avg3_spread'] <= 0.147 and m['m_h'] <= 2.400)

@rule('WL-R10', 'R', 'B', 'wl',
      '立博让方变化>0.136 + 立博初盘让方>2.100 → OOS 76.0%(n=50)')
def _(m):
    return (m['l_hc'] > 0.136 and m['l_ih'] > 2.100)

@rule('WL-R11', 'R', 'B', 'wl',
      '立博让方变化>0.136 + 立博初盘让方>2.200 → OOS 75.0%(n=44)')
def _(m):
    return (m['l_hc'] > 0.136 and m['l_ih'] > 2.200)

@rule('T-R12', 'R', 'B', 'wml',
      '澳门受让方<=2.500 + 威立让方变化差<=-0.014 → OOS 74.6%(n=59)')
def _(m):
    return (m['m_r'] <= 2.500 and m['wl_hc_diff'] <= -0.014)

@rule('T-R13', 'R', 'B', 'wml',
      '三公司受让方均值<=2.587 + 澳门初盘受让方>2.570 → OOS 74.2%(n=66)')
def _(m):
    return (m['avg3_r'] <= 2.587 and m['m_ir'] > 2.570)

@rule('WL-R14', 'R', 'B', 'wl',
      '立博受让方<=2.600 + 威廉初盘返还率<=89.810 → OOS 74.1%(n=85)')
def _(m):
    return (m['l_r'] <= 2.600 and m['w_irr'] <= 89.810)

@rule('WL-R15', 'R', 'B', 'wl',
      '立博受让方<=2.600 + 威廉初盘返还率<=89.410 → OOS 73.8%(n=65)')
def _(m):
    return (m['l_r'] <= 2.600 and m['w_irr'] <= 89.410)

@rule('T-R16', 'R', 'B', 'wml',
      '澳门初盘受让方<=2.680 + 立博让方变化>0.129 → OOS 73.5%(n=68)')
def _(m):
    return (m['m_ir'] <= 2.680 and m['l_hc'] > 0.129)

@rule('D-R17', 'R', 'B', 'wm',
      '澳门受让方<=2.500 + 澳门初盘受让方>2.570 → OOS 73.4%(n=79)')
def _(m):
    return (m['m_r'] <= 2.500 and m['m_ir'] > 2.570)

@rule('WL-R18', 'R', 'B', 'wl',
      '立博赔率差<=0.170 + 威廉初盘返还率<=89.810 → OOS 73.3%(n=86)')
def _(m):
    return (m['l_spread'] <= 0.170 and m['w_irr'] <= 89.810)

@rule('D-R19', 'R', 'B', 'wm',
      '威廉让方>2.500 + 威澳返还率差<=3.280 → OOS 73.1%(n=108)')
def _(m):
    return (m['w_h'] > 2.500 and m['wm_crr_diff'] <= 3.280)

@rule('WL-R20', 'R', 'B', 'wl',
      '立博受让方变化<=-0.054 + 立博初盘让方>2.300 → OOS 72.6%(n=62)')
def _(m):
    return (m['l_rc'] <= -0.054 and m['l_ih'] > 2.300)

@rule('T-R21', 'R', 'B', 'wml',
      '三公司赔率差均值<=0.147 + 威澳返还率差>2.480 → OOS 72.5%(n=153)')
def _(m):
    return (m['avg3_spread'] <= 0.147 and m['wm_crr_diff'] > 2.480)

@rule('WL-R22', 'R', 'B', 'wl',
      '威廉让方>2.400 + 立博让方变化>0.129 → OOS 72.5%(n=102)')
def _(m):
    return (m['w_h'] > 2.400 and m['l_hc'] > 0.129)

@rule('T-R23', 'R', 'B', 'wml',
      '澳门初盘受让方<=2.910 + 立博让方变化>0.129 → OOS 72.3%(n=101)')
def _(m):
    return (m['m_ir'] <= 2.910 and m['l_hc'] > 0.129)

@rule('D-R24', 'R', 'B', 'wm',
      '威廉赔率差<=0.180 + 威廉初盘返还率<=89.810 → OOS 72.2%(n=79)')
def _(m):
    return (m['w_spread'] <= 0.180 and m['w_irr'] <= 89.810)

@rule('T-R25', 'R', 'B', 'wml',
      '三公司赔率差均值<=0.147 + 威澳返还率差<=3.280 → OOS 72.1%(n=129)')
def _(m):
    return (m['avg3_spread'] <= 0.147 and m['wm_crr_diff'] <= 3.280)
