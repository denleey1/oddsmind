// 欧核数据分析 - JavaScript 主文件

// 全局变量
let allMatches = [];
let currentMatchId = null;
let refreshInterval = null;

// API基础URL
const API_BASE = '/api';

// 完整公司映射 - 包含所有352家活跃公司
const COMPANY_MAPPING = {
    '1': '公司_1',
    '2': 'Betfai*(英国)',
    '4': 'Nordic*(马恩岛)',
    '16': '10*(英国)',
    '18': '12*(菲律宾)',
    '30': 'Sazk*(捷克)',
    '34': '公司_34',
    '38': 'Tipsport*(斯洛伐克)',
    '60': 'ST*(波兰)',
    '70': 'Exp*(瑞典)',
    '73': 'Fon*(俄罗斯)',
    '80': '澳*',
    '81': '伟*(直布罗陀)',
    '82': '立*(英国)',
    '87': 'Gold*(马耳它)',
    '88': 'Cora*(英国)',
    '90': '易*(安提瓜和巴布达)',
    '97': 'Nik*(斯洛伐克)',
    '104': 'Interwet*(塞浦路斯)',
    '110': 'SNA*(意大利)',
    '113': 'Veikk*(芬兰)',
    '115': '威*(英国)',
    '121': '公司_121',
    '124': '公司_124',
    '136': 'BoDo*(哥斯达黎加)',
    '145': 'Tipsp*(捷克)',
    '146': 'Intert*(安提瓜和巴布达)',
    '156': 'Betfre*(英国)',
    '159': '公司_159',
    '167': 'sky*(英国)',
    '173': 'bet-at-h*(马尔他)',
    '177': 'Pinna*(荷兰)',
    '180': 'Nor*(挪威)',
    '255': 'Bwi*(奥地利)',
    '281': '36*(英国)',
    '282': 'Bet*(英属直布罗陀)',
    '352': 'Matchb*(安提瓜和巴布达)',
    '354': 'Boylespo*(马恩岛)',
    '370': '公司_370',
    '384': '公司_384',
    '386': '优胜*(马耳他)',
    '422': '博天*(瓦努阿图)',
    '432': '香港马*(中国香港)',
    '436': '公司_436',
    '450': '公司_450',
    '462': 'Bets*(哥斯达黎加)',
    '463': 'BetCl*(英国)',
    '474': '利*(英国)',
    '482': 'Betwa*(直布罗陀)',
    '494': 'Betsson Sportsb*(英国)',
    '499': '金宝*(马恩岛)',
    '517': '明*(菲律宾)',
    '520': 'Meridian*(爱尔兰)',
    '527': 'Tip*(奥地利)',
    '529': 'TopSp*(意大利)',
    '537': 'Bet3*(英国)',
    '540': 'Doxx*(马耳他)',
    '545': 'Crow*',
    '567': '公司_567',
    '571': '公司_571',
    '573': '公司_573',
    '577': 'gioco digit*(意大利)',
    '580': 'Euro*.it(意大利)',
    '591': '公司_591',
    '601': '公司_601',
    '604': '公司_604',
    '613': 'Sports*(澳大利亚)',
    '616': '888Sp*(直布罗陀)',
    '623': 'Dansk Tipstjene*(丹麦)',
    '641': 'Betal*(马耳他)',
    '646': 'PariMa*(俄罗斯)',
    '649': 'IBC*(哥斯达黎加)',
    '656': 'Pamestih*(希腊)',
    '657': 'idda*(土耳其)',
    '659': '盈*(菲律宾)',
    '660': 'Titan*(英属维尔京群岛)',
    '665': 'Bets*(瑞典)',
    '669': 'Germania Sp*(德国)',
    '680': 'Stanley*(马尔他)',
    '686': 'BWi*.it(意大利)',
    '695': 'CashPo*(奥地利)',
    '706': 'Sports*.com.au(澳大利亚)',
    '708': 'Uni*.it(意大利)',
    '709': '公司_709',
    '717': 'Hrvatska Lutr*(克罗地亚)',
    '723': 'Bwi*.fr(法国)',
    '729': 'Ifort*.eu',
    '733': '公司_733',
    '737': 'SuperSp*',
    '741': '公司_741',
    '742': 'betcl*.fr(法国)',
    '750': 'Parions*',
    '751': 'PM*(法国)',
    '755': '公司_755',
    '772': '32Red*(直布罗陀)',
    '775': 'Betonl*',
    '777': '1Be*(直布罗陀)',
    '791': 'Sisa*(意大利)',
    '798': 'Dafa*(菲律宾)',
    '800': '马*(荷属安的列斯群岛)',
    '808': 'Betc*(俄罗斯)',
    '812': 'Efbe*(马耳他)',
    '814': '公司_814',
    '816': 'Marathonb*(俄罗斯)',
    '825': 'Swe*(瑞典)',
    '826': 'Paddy Po*(爱尔兰)',
    '827': 'BetC*.fr(法国)',
    '829': 'BetSo*',
    '832': 'Com*',
    '834': '公司_834',
    '836': '公司_836',
    '843': 'Tony*(马耳他)',
    '844': '公司_844',
    '845': 'Uni*.fr(法国)',
    '850': '公司_850',
    '854': 'Denm*(丹麦)',
    '872': 'Betf*(意大利)',
    '874': 'Bov*',
    '886': 'Mozz*',
    '903': 'Stoixi*(希腊)',
    '908': '公司_908',
    '909': '公司_909',
    '912': 'Etot*(波兰)',
    '925': 'Sprots*',
    '932': 'Evo*',
    '933': 'bwi*.es',
    '934': 'PA*.es',
    '937': 'BetIS*',
    '939': '公司_939',
    '941': '公司_941',
    '943': 'Bov*.lv',
    '945': 'Domus*.it(意大利)',
    '947': 'Five*.it(意大利)',
    '956': '公司_956',
    '963': '公司_963',
    '966': 'Sport*.it',
    '970': '公司_970',
    '972': '公司_972',
    '974': 'VBe*(库拉索)',
    '976': '18*',
    '984': 'Sprea*',
    '986': 'PlanetWin*',
    '988': '公司_988',
    '990': 'pinn*',
    '991': 'Net*.fr',
    '992': '公司_992',
    '996': 'CMD*.com',
    '997': 'Norsk tipt*(挪威)',
    '1017': 'BetVic*',
    '1019': '公司_1019',
    '1020': '公司_1020',
    '1035': 'Bet90*',
    '1036': 'Betfair AU*',
    '1046': 'Svenska S*',
    '1047': '1xBe*',
    '1054': '公司_1054',
    '1055': 'Betfair Excha*',
    '1057': '公司_1057',
    '1064': '公司_1064',
    '1067': '公司_1067',
    '1069': 'Wina*.fr',
    '1070': 'Winline*',
    '1072': '公司_1072',
    '1073': '公司_1073',
    '1074': 'Wina*.com',
    '1089': '公司_1089',
    '1096': 'Betb*',
    '1098': '公司_1098',
    '1099': '公司_1099',
    '1103': 'Leove*',
    '1104': 'Liga Sta*',
    '1105': '公司_1105',
    '1107': '公司_1107',
    '1108': '公司_1108',
    '1116': '公司_1116',
    '1120': 'iFort*.cz',
    '1121': '公司_1121',
    '1124': 'Vulkan*',
    '1127': '公司_1127',
    '1129': '竞彩官*',
    '1131': '公司_1131',
    '1132': 'Cool*',
    '1135': 'Ladbro*.au',
    '1138': '公司_1138',
    '1142': '公司_1142',
    '1149': 'BetReb*',
    '1154': 'Net*.it',
    '1155': '公司_1155',
    '1156': '公司_1156',
    '1159': '公司_1159',
    '1161': '公司_1161',
    '1162': '公司_1162',
    '1166': '公司_1166',
    '1167': 'Bet2*',
    '1183': '公司_1183',
    '1184': '公司_1184',
    '1207': 'ScommesseIta*',
    '1210': 'Bet9j* (尼日利亚)',
    '1212': 'Pokerst*',
    '1219': '公司_1219',
    '1220': '公司_1220',
    '1222': '公司_1222',
    '1225': '公司_1225',
    '1226': '公司_1226',
    '1228': '公司_1228',
    '1229': '22Be*',
    '1231': 'LeonB*',
    '1232': '公司_1232',
    '1237': '公司_1237',
    '1238': '公司_1238',
    '1243': 'Beta*(德国)',
    '1244': '公司_1244',
    '1245': 'NE*.bet',
    '1246': '公司_1246',
    '1247': '公司_1247',
    '1249': 'Fand*',
    '1250': '公司_1250',
    '1251': 'FEZ*',
    '1252': '公司_1252',
    '1253': '公司_1253',
    '1254': '10x10*',
    '1255': 'BetInA*',
    '1256': 'GGBE*',
    '1257': 'Leo*.ru',
    '1258': 'Marathon*.ru',
    '1259': '公司_1259',
    '1261': 'col*',
    '1262': 'WPla*',
    '1264': 'Sporty*',
    '1265': 'BetK*',
    '1269': 'Ta*.co.nz',
    '1270': 'Oly*',
    '1271': 'Marathon*.es',
    '1272': 'Inka*',
    '1275': 'TippMi*',
    '1276': 'LON*',
    '1277': 'LoterieRoma*',
    '1278': 'SportP*.it',
    '1279': '公司_1279',
    '1280': 'FDJO*',
    '1281': '公司_1281',
    '1282': 'Superma*.com.uy',
    '1284': 'LeoVe*.it',
    '1285': '公司_1285',
    '1286': '公司_1286',
    '1287': '公司_1287',
    '1289': 'Joabe*(法国)',
    '1290': '公司_1290',
    '1291': '公司_1291',
    '1292': '公司_1292',
    '1293': '公司_1293',
    '1294': '公司_1294',
    '1295': 'DoubleBe*',
    '1296': '公司_1296',
    '1297': '公司_1297',
    '1298': '公司_1298',
    '1299': 'Bumbe*',
    '1300': 'YaJueg*',
    '1301': 'Winlin*.ru(俄罗斯)',
    '1302': '公司_1302',
    '1303': 'LSbe*',
    '1304': 'Betwa*.it(意大利)',
    '1305': 'Betwa*.es(西班牙)',
    '1306': 'Bet Sensatio*',
    '1308': 'Vbe*(法国)',
    '1309': 'Vbe*(乌克兰)',
    '1310': 'Gbet*(南非)',
    '1311': 'Bahislio*(土耳其)',
    '1312': 'Suprabet*',
    '1313': '公司_1313',
    '1314': '公司_1314',
    '1315': 'Marathonbe*.it(意大利)',
    '1316': '公司_1316',
    '1318': 'Paripes*',
    '1319': 'Melbe*',
    '1321': 'Megapar*',
    '1322': 'Stoixima*(塞浦路斯)',
    '1323': '公司_1323',
    '1324': 'N1 BE*',
    '1325': '公司_1325',
    '1326': '公司_1326',
    '1329': '公司_1329',
    '1330': '公司_1330',
    '1331': 'Casinobarcelon*.es(西班牙)',
    '1332': 'Beta*(巴西)',
    '1333': 'Everygam*',
    '1334': 'BetBoo*.ru',
    '1335': 'RojaBe*',
    '1336': 'ReloadBe*',
    '1337': '公司_1337',
    '1338': '公司_1338',
    '1339': '公司_1339',
    '1340': 'Menge*.ru',
    '1341': 'JOKERBE*',
    '1342': '公司_1342',
    '1343': 'pris*(俄罗斯)',
    '1344': '公司_1344',
    '1346': 'BetPla*',
    '1347': '公司_1347',
    '1349': 'Uni*.se(瑞典)',
    '1350': '公司_1350',
    '1351': 'Bet-o-be*',
    '1352': 'Vbe*(加拿大)',
    '1353': 'Pin-U*',
    '1354': 'BeOnBe*',
    '1355': 'Betibe*',
    '1356': 'BetBoo*',
    '1357': 'Roosterbe*',
    '1358': 'Cloudbe*',
    '1359': '1xBi*',
    '1360': 'spinbette*',
    '1361': 'Фонбе*',
    '1362': '888Star*',
    '1363': 'N1BE*.it(意大利)',
    '1364': 'N1BE*.de(德国)',
    '1365': 'N1BE*.se(瑞典)',
    '1366': '1wi*',
    '1367': 'Stak*',
    '1368': 'GGBe*.ua(乌克兰)',
    '1370': '20Be*',
    '1371': 'Ivibe*',
    '1372': 'Powbe*',
    '1373': 'Vav*',
    '1374': 'Campobe*',
    '1375': 'Cashwi*',
    '1376': 'ToonieBe*',
    '1377': 'Betan*',
    '1378': 'BC.Gam*',
    '1379': 'Betobe*',
    '1380': 'PowerPla*',
    '1381': 'All British Casin*',
    '1382': '公司_1382',
    '1383': 'BetMG*',
    '1384': 'Most*',
    '1386': '公司_1386',
    '1387': 'Mystak*',
    '1389': 'Nine Casin*',
    '1390': '公司_1390',
    '1391': 'Bet36* NJ',
    '1392': '公司_1392',
    '1393': 'Weltbe*',
    '1394': 'Freshbe*',
    '1395': '公司_1395',
    '1396': 'Coder*',
    '1397': 'Jackbi*',
    '1398': 'Goldenbe*',
    '1399': '4rabe*',
    '1400': 'Borgat*',
    '1401': 'Be*UK',
    '1403': '公司_1403',
    '1404': 'Cosmobe*',
    '1405': '公司_1405'
};

const CONFIDENCE_ZONE_TABLES = Object.freeze(
    {
      "\u4fe1\u5fc3\u5145\u8db3": {
        "D": {
          "zone": "\u97ec\u5149\u76d8",
          "effect": [
            "\u5f3a\u5316\u4fe1\u5fc3",
            "\u5347\u8d54\u4ed8"
          ]
        },
        "C": {
          "zone": "\u9ad8\u5f00\u76d8",
          "effect": [
            "\u5f3a\u5316\u4fe1\u5fc3",
            "\u5347\u8d54\u4ed8"
          ]
        },
        "B": {
          "zone": "\u5b9e\u5f00\u76d8\u00b7\u62ac\u9ad8\u6c34\u4f4d",
          "effect": [
            "\u5229\u8bf1"
          ]
        },
        "A": {
          "zone": "\u5b9e\u5f00\u76d8\u00b7\u4e2d\u5eb8\u6c34\u4f4d",
          "effect": [
            "\u4e0d\u53d8"
          ]
        },
        "S": {
          "zone": "\u5b9e\u5f00\u76d8\u00b7\u62c9\u4f4e\u6c34\u4f4d",
          "effect": [
            "\u5f31\u5316\u4fe1\u5fc3",
            "\u964d\u8d54\u4ed8"
          ]
        },
        "SS": {
          "zone": "\u4f4e\u5f00\u76d8",
          "effect": [
            "\u5f31\u5316\u4fe1\u5fc3"
          ]
        },
        "SSS": {
          "zone": "\u8d85\u5b9e\u76d8",
          "effect": [
            "\u5f31\u5316\u4fe1\u5fc3",
            "\u964d\u8d54\u4ed8"
          ]
        }
      },
      "\u4fe1\u5fc3\u4e2d\u4e0a": {
        "E": {
          "zone": "\u97ec\u5149\u76d8",
          "effect": [
            "\u5f3a\u5316\u4fe1\u5fc3",
            "\u5347\u8d54\u4ed8"
          ]
        },
        "D": {
          "zone": "\u9ad8\u5f00\u76d8",
          "effect": [
            "\u5f3a\u5316\u4fe1\u5fc3",
            "\u5347\u8d54\u4ed8"
          ]
        },
        "C": {
          "zone": "\u5b9e\u5f00\u76d8\u00b7\u62ac\u9ad8\u6c34\u4f4d",
          "effect": [
            "\u5229\u8bf1"
          ]
        },
        "B": {
          "zone": "\u5b9e\u5f00\u76d8\u00b7\u4e2d\u5eb8\u6c34\u4f4d",
          "effect": [
            "\u4e0d\u53d8"
          ]
        },
        "A": {
          "zone": "\u5b9e\u5f00\u76d8\u00b7\u62c9\u4f4e\u6c34\u4f4d",
          "effect": [
            "\u5f31\u5316\u4fe1\u5fc3",
            "\u964d\u8d54\u4ed8"
          ]
        },
        "S": {
          "zone": "\u4f4e\u5f00\u76d8",
          "effect": [
            "\u5f31\u5316\u4fe1\u5fc3"
          ]
        },
        "SS": {
          "zone": "\u8d85\u5b9e\u76d8",
          "effect": [
            "\u5f31\u5316\u4fe1\u5fc3",
            "\u964d\u8d54\u4ed8"
          ]
        }
      },
      "\u4fe1\u5fc3\u4e2d\u5eb8": {
        "S": {
          "zone": "\u97ec\u5149\u76d8",
          "effect": [
            "\u5f31\u5316\u4fe1\u5fc3",
            "\u5347\u8d54\u4ed8"
          ]
        },
        "A": {
          "zone": "\u9ad8\u5f00\u76d8",
          "effect": [
            "\u5f31\u5316\u4fe1\u5fc3",
            "\u5347\u8d54\u4ed8"
          ]
        },
        "B": {
          "zone": "\u5b9e\u5f00\u76d8\u00b7\u62ac\u9ad8\u6c34\u4f4d",
          "effect": [
            "\u963b"
          ]
        },
        "C": {
          "zone": "\u5b9e\u5f00\u76d8\u00b7\u4e2d\u5eb8\u6c34\u4f4d",
          "effect": [
            "\u4e0d\u53d8"
          ]
        },
        "D": {
          "zone": "\u5b9e\u5f00\u76d8\u00b7\u62c9\u4f4e\u6c34\u4f4d",
          "effect": [
            "\u5f3a\u5316\u4fe1\u5fc3",
            "\u964d\u8d54\u4ed8"
          ]
        },
        "E": {
          "zone": "\u4f4e\u5f00\u76d8",
          "effect": [
            "\u5f3a\u5316\u4fe1\u5fc3"
          ]
        },
        "F": {
          "zone": "\u8d85\u5b9e\u76d8",
          "effect": [
            "\u5f3a\u5316\u4fe1\u5fc3",
            "\u964d\u8d54\u4ed8"
          ]
        }
      },
      "\u4fe1\u5fc3\u4e2d\u4e0b": {
        "SS": {
          "zone": "\u97ec\u5149\u76d8",
          "effect": [
            "\u5f31\u5316\u4fe1\u5fc3",
            "\u5347\u8d54\u4ed8"
          ]
        },
        "S": {
          "zone": "\u9ad8\u5f00\u76d8",
          "effect": [
            "\u5f31\u5316\u4fe1\u5fc3",
            "\u5347\u8d54\u4ed8"
          ]
        },
        "A": {
          "zone": "\u5b9e\u5f00\u76d8\u00b7\u62ac\u9ad8\u6c34\u4f4d",
          "effect": [
            "\u963b"
          ]
        },
        "B": {
          "zone": "\u5b9e\u5f00\u76d8\u00b7\u4e2d\u5eb8\u6c34\u4f4d",
          "effect": [
            "\u4e0d\u53d8"
          ]
        },
        "C": {
          "zone": "\u5b9e\u5f00\u76d8\u00b7\u62c9\u4f4e\u6c34\u4f4d",
          "effect": [
            "\u5f3a\u5316\u4fe1\u5fc3",
            "\u964d\u8d54\u4ed8"
          ]
        },
        "D": {
          "zone": "\u4f4e\u5f00\u76d8",
          "effect": [
            "\u5f3a\u5316\u4fe1\u5fc3"
          ]
        },
        "E": {
          "zone": "\u8d85\u5b9e\u76d8",
          "effect": [
            "\u5f3a\u5316\u4fe1\u5fc3",
            "\u964d\u8d54\u4ed8"
          ]
        }
      },
      "\u4fe1\u5fc3\u4e0d\u8db3": {
        "SSS": {
          "zone": "\u97ec\u5149\u76d8",
          "effect": [
            "\u5f31\u5316\u4fe1\u5fc3",
            "\u5347\u8d54\u4ed8"
          ]
        },
        "SS": {
          "zone": "\u9ad8\u5f00\u76d8",
          "effect": [
            "\u5f31\u5316\u4fe1\u5fc3",
            "\u5347\u8d54\u4ed8"
          ]
        },
        "S": {
          "zone": "\u5b9e\u5f00\u76d8\u00b7\u62ac\u9ad8\u6c34\u4f4d",
          "effect": [
            "\u963b"
          ]
        },
        "A": {
          "zone": "\u5b9e\u5f00\u76d8\u00b7\u4e2d\u5eb8\u6c34\u4f4d",
          "effect": [
            "\u4e0d\u53d8"
          ]
        },
        "B": {
          "zone": "\u5b9e\u5f00\u76d8\u00b7\u62c9\u4f4e\u6c34\u4f4d",
          "effect": [
            "\u5f3a\u5316\u4fe1\u5fc3",
            "\u964d\u8d54\u4ed8"
          ]
        },
        "C": {
          "zone": "\u4f4e\u5f00\u76d8",
          "effect": [
            "\u5f3a\u5316\u4fe1\u5fc3"
          ]
        },
        "D": {
          "zone": "\u8d85\u5b9e\u76d8",
          "effect": [
            "\u5f3a\u5316\u4fe1\u5fc3",
            "\u964d\u8d54\u4ed8"
          ]
        }
      }
    }
);

const CONFIDENCE_WATER_BUCKETS = Object.freeze(
    {
      "\u62ac\u9ad8\u6c34\u4f4d": [
        "\u8d85\u9ad8\u6c34",
        "\u9ad8\u6c34",
        "\u4e2d\u9ad8\u6c34"
      ],
      "\u4e2d\u5eb8\u6c34\u4f4d": [
        "\u4e2d\u6c34"
      ],
      "\u62c9\u4f4e\u6c34\u4f4d": [
        "\u4e2d\u4f4e\u6c34",
        "\u4f4e\u6c34",
        "\u8d85\u4f4e\u6c34"
      ]
    }
);

const CONFIDENCE_BAND_ALIASES = Object.freeze(
    {
      "\u4e2d\u5eb8\u4fe1\u5fc3": "\u4e2d\u5eb8\u4fe1\u5fc3",
      "\u4fe1\u5fc3\u4e2d\u5eb8": "\u4e2d\u5eb8\u4fe1\u5fc3",
      "\u4fe1\u5fc3\u5145\u8db3": "\u4fe1\u5fc3\u5145\u8db3",
      "\u4fe1\u5fc3\u4e2d\u4e0a": "\u4fe1\u5fc3\u5145\u8db3",
      "\u6781\u81f4\u4fe1\u5fc3": "\u4fe1\u5fc3\u5145\u8db3",
      "\u4fe1\u5fc3\u4e0d\u8db3": "\u4fe1\u5fc3\u4e0d\u8db3",
      "\u4fe1\u5fc3\u4e2d\u4e0b": "\u4fe1\u5fc3\u4e0d\u8db3",
      "\u6b20\u7f3a\u4fe1\u5fc3": "\u4fe1\u5fc3\u4e0d\u8db3"
    }
);

const CONFIDENCE_MAP_SUFFICIENT_TO_MIDDLE = Object.freeze(
    {
      "\u65e0": "\u8d85\u97ec\u5e73",
      "\u8d85\u97ec\u5e73": "\u97ec\u5f00\u5e73",
      "\u97ec\u5f00\u5e73": "\u9ad8\u5f00\u5e73",
      "\u9ad8\u5f00\u5e73": "\u5e73\u5b9e\u9ad8",
      "\u5b9e\u5f00\u5e73": "\u5e73\u4e2d\u5eb8",
      "\u4f4e\u5f00\u5e73": "\u5e73\u5b9e\u4f4e",
      "\u8d85\u5b9e\u5e73": "\u4f4e\u5f00\u5e73",
      "\u8d85\u6563\u5e73": "\u8d85\u5b9e\u5e73",
      "\u8d85\u6df1\u5e73": "\u8d85\u6563\u5e73"
    }
);

const CONFIDENCE_MAP_INSUFFICIENT_TO_MIDDLE = Object.freeze(
    {
      "\u65e0": "\u8d85\u6df1\u5e73",
      "\u97ec\u5f00\u5e73": "\u8d85\u97ec\u5e73",
      "\u9ad8\u5f00\u5e73": "\u97ec\u5f00\u5e73",
      "\u5e73\u5b9e\u9ad8": "\u9ad8\u5f00\u5e73",
      "\u5e73\u4e2d\u5eb8": "\u5e73\u5b9e\u9ad8",
      "\u5e73\u5b9e\u4f4e": "\u5e73\u4e2d\u5eb8",
      "\u4f4e\u5f00\u5e73": "\u5e73\u5b9e\u4f4e",
      "\u8d85\u5b9e\u5e73": "\u4f4e\u5f00\u5e73",
      "\u8d85\u6563\u5e73": "\u8d85\u5b9e\u5e73",
      "\u8d85\u6df1\u5e73": "\u8d85\u6563\u5e73",
      "\u5b9e\u5f00\u5e73": "\u9ad8\u5f00\u5e73"
    }
);

function findConfidenceWaterBucket(text) {
    const normalized = String(text || '').replace(/\s+/g, '');
    if (!normalized) {
        return null;
    }

    for (const [bucket, keywords] of Object.entries(CONFIDENCE_WATER_BUCKETS)) {
        if (keywords.some((keyword) => normalized.includes(keyword))) {
            return bucket;
        }
    }
    return null;
}

function normalizeConfidenceZone(textRaw) {
    const t = String(textRaw || '').replace(/\s+/g, '');
    if (!t) {
        return null;
    }

    if (/(实开盘|实开区)/.test(t)) {
        const bucket = findConfidenceWaterBucket(t) || '中庸水位';
        return { zone: `实开盘·${bucket}` };
    }

    if (/(韬|韬光)/.test(t)) {
        return { zone: '韬光盘' };
    }
    if (/(高开盘|高开区)/.test(t)) {
        return { zone: '高开盘' };
    }
    if (/(低开盘|低开区)/.test(t)) {
        return { zone: '低开盘' };
    }
    if (/(超实盘|超实区)/.test(t)) {
        return { zone: '超实盘' };
    }

    return null;
}

function lookupConfidenceByText(band, zoneText) {
    const normalized = normalizeConfidenceZone(zoneText);
    if (!normalized) {
        return null;
    }
    const group = CONFIDENCE_ZONE_TABLES[band];
    if (!group) {
        return null;
    }

    for (const [grade, details] of Object.entries(group)) {
        if (details.zone === normalized.zone) {
            return { grade, zone: details.zone, effect: details.effect };
        }
    }

    return { grade: null, zone: normalized.zone, effect: null };
}

function normalizeConfidenceBand(band) {
    if (!band) {
        return null;
    }
    const normalized = String(band).replace(/\s+/g, '');
    if (CONFIDENCE_BAND_ALIASES[normalized]) {
        return CONFIDENCE_BAND_ALIASES[normalized];
    }
    if (/充足|充分|中上|偏上|较强|强|极/.test(normalized)) {
        return '信心充足';
    }
    if (/不足|欠|中下|偏下|较弱|弱/.test(normalized)) {
        return '信心不足';
    }
    if (/中庸|均衡|平衡|普通|一般/.test(normalized)) {
        return '中庸信心';
    }
    return null;
}

function normalizeFlatPositionKey(position) {
    if (position === null || position === undefined) {
        return null;
    }
    let text = String(position).replace(/\s+/g, '');
    if (!text || text === '--') {
        return null;
    }
    text = text
        .replace(/[·•·\-]/g, '')
        .replace(/[()（）]/g, '')
        .replace(/\//g, '')
        .replace(/　/g, '');
    return text;
}

function toMiddleFlatPosition(band, position) {
    const normalizedBand = normalizeConfidenceBand(band);
    const normalizedPosition = normalizeFlatPositionKey(position);
    if (!normalizedBand || !normalizedPosition) {
        return null;
    }

    if (normalizedBand === '中庸信心') {
        return normalizedPosition;
    }
    if (normalizedBand === '信心充足') {
        return CONFIDENCE_MAP_SUFFICIENT_TO_MIDDLE[normalizedPosition] || null;
    }
    if (normalizedBand === '信心不足') {
        return CONFIDENCE_MAP_INSUFFICIENT_TO_MIDDLE[normalizedPosition] || null;
    }

    return null;
}

function formatConfidenceEffect(effect) {
    if (!effect || effect.length === 0) {
        return '--';
    }
    return effect.join('/');
}

function escapeHtml(value) {
    if (value === null || value === undefined) {
        return '';
    }
    return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

function escapeHtmlAttr(value) {
    if (value === null || value === undefined) {
        return '';
    }
    return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

const BETTING_CONFIDENCE_LEVEL_ALIASES = Object.freeze({
    '欠缺信心': '欠缺信心',
    '信心欠缺': '欠缺信心',
    '信心不足': '信心不足',
    '欠缺': '欠缺信心',
    '不足': '信心不足',
    '信心中低': '信心中低',
    '信心中下': '信心中下',
    '信心中庸': '信心中庸',
    '信心中上': '信心中上',
    '信心中高': '信心中高',
    '信心充足': '信心充足',
    '极致信心': '极致信心'
});

const BETTING_PRESSURE_RULES = Object.freeze({
    '超韬利盘': {
        '欠缺信心': -2.0,
        '信心不足': -1.0,
        '信心中低': -0.5,
        '信心中下': 0.0,
        '信心中庸': { lower: 0.5, higher: -0.5 },
        '信心中上': 0.0,
        '信心中高': 0.5,
        '信心充足': 1.0,
        '极致信心': 2.0,
    },
    '超韬盘中上水': {
        '欠缺信心': -1.875,
        '信心不足': -1.5,
        '信心中低': -0.75,
        '信心中下': -0.25,
        '信心中庸': { lower: 0.25, higher: -0.25 },
        '信心中上': 0.25,
        '信心中高': 0.75,
        '信心充足': 1.5,
        '极致信心': 1.875,
    },
    '超韬盘中下水': {
        '欠缺信心': -1.75,
        '信心不足': -2.0,
        '信心中低': -1.25,
        '信心中下': -0.75,
        '信心中庸': { lower: -0.25, higher: 0.25 },
        '信心中上': 0.75,
        '信心中高': 1.25,
        '信心充足': 2.0,
        '极致信心': 1.75,
    },
    '韬光盘超高水': {
        '欠缺信心': -1.625,
        '信心不足': -1.9,
        '信心中低': -1.75,
        '信心中下': -1.25,
        '信心中庸': { lower: -0.75, higher: 0.75 },
        '信心中上': 1.25,
        '信心中高': 1.75,
        '信心充足': 1.9,
        '极致信心': 1.625,
    },
    '韬光盘高水': {
        '欠缺信心': -1.5,
        '信心不足': -1.75,
        '信心中低': -2.0,
        '信心中下': -1.5,
        '信心中庸': { lower: -1.0, higher: 1.0 },
        '信心中上': 1.5,
        '信心中高': 2.0,
        '信心充足': 1.75,
        '极致信心': 1.5,
    },
    '韬光盘中高水': {
        '欠缺信心': -1.375,
        '信心不足': -1.6,
        '信心中低': -1.8,
        '信心中下': -1.75,
        '信心中庸': { lower: -1.25, higher: 1.25 },
        '信心中上': 1.75,
        '信心中高': 1.8,
        '信心充足': 1.6,
        '极致信心': 1.375,
    },
    '韬光盘中水': {
        '欠缺信心': -1.25,
        '信心不足': -1.45,
        '信心中低': -1.65,
        '信心中下': -2.0,
        '信心中庸': { lower: -1.5, higher: 1.5 },
        '信心中上': 2.0,
        '信心中高': 1.65,
        '信心充足': 1.45,
        '极致信心': 1.25,
    },
    '韬光盘中低水': {
        '欠缺信心': -1.125,
        '信心不足': -1.3,
        '信心中低': -1.5,
        '信心中下': -1.8,
        '信心中庸': { lower: -1.75, higher: 1.75 },
        '信心中上': 1.8,
        '信心中高': 1.5,
        '信心充足': 1.3,
        '极致信心': 1.125,
    },
    '韬光盘低水': {
        '欠缺信心': -1.0,
        '信心不足': -1.15,
        '信心中低': -1.3,
        '信心中下': -1.6,
        '信心中庸': { lower: -2.0, higher: 2.0 },
        '信心中上': 1.6,
        '信心中高': 1.3,
        '信心充足': 1.15,
        '极致信心': 1.0,
    },
    '韬光盘超低水': {
        '欠缺信心': -0.875,
        '信心不足': -1.0,
        '信心中低': -1.15,
        '信心中下': -1.4,
        '信心中庸': { lower: -1.75, higher: 1.75 },
        '信心中上': 1.4,
        '信心中高': 1.15,
        '信心充足': 1.0,
        '极致信心': 0.875,
    },
    '高开盘中高水': {
        '欠缺信心': -0.75,
        '信心不足': -0.9,
        '信心中低': -1.0,
        '信心中下': -1.2,
        '信心中庸': { lower: -1.5, higher: 1.5 },
        '信心中上': 1.2,
        '信心中高': 1.0,
        '信心充足': 0.9,
        '极致信心': 0.75,
    },
    '高开盘中水': {
        '欠缺信心': -0.625,
        '信心不足': -0.75,
        '信心中低': -0.8,
        '信心中下': -1.0,
        '信心中庸': { lower: -1.25, higher: 1.25 },
        '信心中上': 1.0,
        '信心中高': 0.8,
        '信心充足': 0.75,
        '极致信心': 0.625,
    },
    '高开盘中低水': {
        '欠缺信心': -0.5,
        '信心不足': -0.6,
        '信心中低': -0.65,
        '信心中下': -0.8,
        '信心中庸': { lower: -1.0, higher: 1.0 },
        '信心中上': 0.8,
        '信心中高': 0.65,
        '信心充足': 0.6,
        '极致信心': 0.5,
    },
    '实开盘超高水': {
        '欠缺信心': -0.375,
        '信心不足': -0.45,
        '信心中低': -0.5,
        '信心中下': -0.6,
        '信心中庸': { lower: -0.75, higher: 0.75 },
        '信心中上': 0.6,
        '信心中高': 0.5,
        '信心充足': 0.45,
        '极致信心': 0.375,
    },
    '实开盘高水': {
        '欠缺信心': -0.25,
        '信心不足': -0.3,
        '信心中低': -0.3,
        '信心中下': -0.4,
        '信心中庸': { lower: -0.5, higher: 0.5 },
        '信心中上': 0.4,
        '信心中高': 0.3,
        '信心充足': 0.3,
        '极致信心': 0.25,
    },
    '实开盘中高水': {
        '欠缺信心': -0.125,
        '信心不足': -0.15,
        '信心中低': -0.15,
        '信心中下': -0.2,
        '信心中庸': { lower: -0.25, higher: 0.25 },
        '信心中上': 0.2,
        '信心中高': 0.15,
        '信心充足': 0.15,
        '极致信心': 0.125,
    },
    '实开盘中水': {
        '欠缺信心': 0.0,
        '信心不足': 0.0,
        '信心中低': 0.0,
        '信心中下': 0.0,
        '信心中庸': { lower: 0.0, higher: 0.0 },
        '信心中上': 0.0,
        '信心中高': 0.0,
        '信心充足': 0.0,
        '极致信心': 0.0,
    },
    '实开盘中低水': {
        '欠缺信心': 0.125,
        '信心不足': 0.15,
        '信心中低': 0.15,
        '信心中下': 0.2,
        '信心中庸': { lower: 0.25, higher: -0.25 },
        '信心中上': -0.2,
        '信心中高': -0.15,
        '信心充足': -0.15,
        '极致信心': -0.125,
    },
    '实开盘低水': {
        '欠缺信心': 0.25,
        '信心不足': 0.3,
        '信心中低': 0.3,
        '信心中下': 0.4,
        '信心中庸': { lower: 0.5, higher: -0.5 },
        '信心中上': -0.4,
        '信心中高': -0.3,
        '信心充足': -0.3,
        '极致信心': -0.25,
    },
    '实开盘超低水': {
        '欠缺信心': 0.375,
        '信心不足': 0.45,
        '信心中低': 0.45,
        '信心中下': 0.6,
        '信心中庸': { lower: 0.75, higher: -0.75 },
        '信心中上': -0.6,
        '信心中高': -0.45,
        '信心充足': -0.45,
        '极致信心': -0.375,
    },
    '低开盘中高水': {
        '欠缺信心': 0.5,
        '信心不足': 0.6,
        '信心中低': 0.6,
        '信心中下': 0.8,
        '信心中庸': { lower: 1.0, higher: -1.0 },
        '信心中上': -0.8,
        '信心中高': -0.6,
        '信心充足': -0.6,
        '极致信心': -0.5,
    },
    '低开盘中水': {
        '欠缺信心': 0.625,
        '信心不足': 0.75,
        '信心中低': 0.75,
        '信心中下': 1.0,
        '信心中庸': { lower: 1.25, higher: -1.25 },
        '信心中上': -1.0,
        '信心中高': -0.75,
        '信心充足': -0.75,
        '极致信心': -0.625,
    },
    '低开盘中低水': {
        '欠缺信心': 0.75,
        '信心不足': 0.9,
        '信心中低': 0.9,
        '信心中下': 1.2,
        '信心中庸': { lower: 1.5, higher: -1.5 },
        '信心中上': -1.2,
        '信心中高': -0.9,
        '信心充足': -0.9,
        '极致信心': -0.75,
    },
    '超实盘超高水': {
        '欠缺信心': 0.875,
        '信心不足': 1.0,
        '信心中低': 1.05,
        '信心中下': 1.4,
        '信心中庸': { lower: 1.75, higher: -1.75 },
        '信心中上': -1.4,
        '信心中高': -1.05,
        '信心充足': -1.0,
        '极致信心': -0.875,
    },
    '超实盘高水': {
        '欠缺信心': 1.0,
        '信心不足': 1.15,
        '信心中低': 1.2,
        '信心中下': 1.6,
        '信心中庸': { lower: 2.0, higher: -2.0 },
        '信心中上': -1.6,
        '信心中高': -1.2,
        '信心充足': -1.15,
        '极致信心': -1.0,
    },
    '超实盘中高水': {
        '欠缺信心': 1.125,
        '信心不足': 1.3,
        '信心中低': 1.35,
        '信心中下': 1.8,
        '信心中庸': { lower: 1.75, higher: -1.75 },
        '信心中上': -1.8,
        '信心中高': -1.35,
        '信心充足': -1.3,
        '极致信心': -1.125,
    },
    '超实盘中水': {
        '欠缺信心': 1.25,
        '信心不足': 1.45,
        '信心中低': 1.5,
        '信心中下': 2.0,
        '信心中庸': { lower: 1.5, higher: -1.5 },
        '信心中上': -2.0,
        '信心中高': -1.5,
        '信心充足': -1.45,
        '极致信心': -1.25,
    },
    '超实盘中低水': {
        '欠缺信心': 1.375,
        '信心不足': 1.6,
        '信心中低': 1.8,
        '信心中下': 1.75,
        '信心中庸': { lower: 1.25, higher: -1.25 },
        '信心中上': -1.75,
        '信心中高': -1.8,
        '信心充足': -1.6,
        '极致信心': -1.375,
    },
    '超实盘低水': {
        '欠缺信心': 1.5,
        '信心不足': 1.75,
        '信心中低': 2.0,
        '信心中下': 1.5,
        '信心中庸': { lower: 1.0, higher: -1.0 },
        '信心中上': -1.5,
        '信心中高': -2.0,
        '信心充足': -1.75,
        '极致信心': -1.5,
    },
    '超实盘超低水': {
        '欠缺信心': 1.625,
        '信心不足': 1.9,
        '信心中低': 1.75,
        '信心中下': 1.25,
        '信心中庸': { lower: 0.75, higher: -0.75 },
        '信心中上': -1.25,
        '信心中高': -1.75,
        '信心充足': -1.9,
        '极致信心': -1.625,
    },
    '超散盘中高水': {
        '欠缺信心': 1.75,
        '信心不足': 2.0,
        '信心中低': 1.5,
        '信心中下': 1.0,
        '信心中庸': { lower: 0.5, higher: -0.5 },
        '信心中上': -1.0,
        '信心中高': -1.5,
        '信心充足': -2.0,
        '极致信心': -1.75,
    },
    '超散盘中水': {
        '欠缺信心': 1.875,
        '信心不足': 1.75,
        '信心中低': 1.25,
        '信心中下': 0.75,
        '信心中庸': { lower: 0.25, higher: -0.25 },
        '信心中上': -0.75,
        '信心中高': -1.25,
        '信心充足': -1.75,
        '极致信心': -1.875,
    },
    '超散盘中低水': {
        '欠缺信心': 2.0,
        '信心不足': 1.5,
        '信心中低': 1.0,
        '信心中下': 0.5,
        '信心中庸': { lower: 0.0, higher: 0.0 },
        '信心中上': -0.5,
        '信心中高': -1.0,
        '信心充足': -1.5,
        '极致信心': -2.0,
    },
    '超散盘低水': {
        '欠缺信心': 1.75,
        '信心不足': 1.25,
        '信心中低': 0.75,
        '信心中下': 0.25,
        '信心中庸': { lower: -0.25, higher: 0.25 },
        '信心中上': -0.25,
        '信心中高': -0.75,
        '信心充足': -1.25,
        '极致信心': -1.75,
    },
    '超深盘中上水': {
        '欠缺信心': 1.15,
        '信心不足': 0.65,
        '信心中低': 0.15,
        '信心中下': -0.35,
        '信心中庸': { lower: -0.85, higher: 0.85 },
        '信心中上': 0.35,
        '信心中高': -0.15,
        '信心充足': -0.65,
        '极致信心': -1.15,
    },
    '超深盘中下水': {
        '欠缺信心': 0.5,
        '信心不足': 0.0,
        '信心中低': -0.5,
        '信心中下': -1.0,
        '信心中庸': { lower: -1.55, higher: 1.5 },
        '信心中上': 1.0,
        '信心中高': 0.5,
        '信心充足': 0.0,
        '极致信心': -0.5,
    },
    '超深诱盘': {
        '欠缺信心': 0.25,
        '信心不足': -0.25,
        '信心中低': -0.75,
        '信心中下': -1.25,
        '信心中庸': { lower: -1.75, higher: 1.75 },
        '信心中上': 1.25,
        '信心中高': 0.75,
        '信心充足': 0.25,
        '极致信心': -0.25,
    }
});



function formatBettingPressureValue(value) {
    if (typeof value !== 'number' || Number.isNaN(value)) {
        return '--';
    }
    let formatted = value.toFixed(2).replace(/\.0+$/, '').replace(/0+$/, '').replace(/\.$/, '');
    if (value > 0 && !formatted.startsWith('+')) {
        formatted = `+${formatted}`;
    }
    return formatted;
}

function normalizeBettingConfidenceLevel(level) {
    if (!level) {
        return null;
    }
    const compact = String(level).replace(/\s+/g, '');
    const direct = BETTING_CONFIDENCE_LEVEL_ALIASES[compact];
    if (direct) {
        return direct;
    }
    if (/欠缺/.test(compact)) return '欠缺信心';
    if (/不足/.test(compact)) return '信心不足';
    if (/极致/.test(compact)) return '极致信心';
    if (/(充足|充分|十足)/.test(compact)) return '信心充足';
    if (/中高/.test(compact)) return '信心中高';
    if (/(中上|偏上|较强|偏强)/.test(compact)) return '信心中上';
    if (/(中庸|均衡|普通|一般|平衡)/.test(compact)) return '信心中庸';
    if (/中下/.test(compact)) return '信心中下';
    if (/中低/.test(compact)) return '信心中低';
    if (/(偏下|较弱|欠佳|偏弱|不佳)/.test(compact)) return '信心中低';
    return compact;
}

function normalizeBettingOddsRangeKey(label) {
    if (!label) {
        return '';
    }
    return String(label)
        .replace(/（.*?）/g, '')
        .replace(/\(.*?\)/g, '')
        .replace(/[·•]/g, '')
        .replace(/开区/g, '开盘')
        .replace(/区/g, '盘')
        .replace(/\s+/g, '')
        .trim();
}

function buildBettingPressureRangeLookup(rules) {
    const lookup = {};
    Object.keys(rules).forEach((ruleKey) => {
        const normalized = normalizeBettingOddsRangeKey(ruleKey);
        if (normalized) {
            if (!lookup[normalized]) {
                lookup[normalized] = ruleKey;
            }
            const noPan = normalized.replace(/盘/g, '');
            if (noPan && !lookup[noPan]) {
                lookup[noPan] = ruleKey;
            }
        }
    });
    return lookup;
}

const BETTING_PRESSURE_RANGE_LOOKUP = Object.freeze(buildBettingPressureRangeLookup(BETTING_PRESSURE_RULES));

function resolveBettingOddsRangeKey(label) {
    const normalized = normalizeBettingOddsRangeKey(label);
    if (!normalized) {
        return null;
    }
    if (BETTING_PRESSURE_RANGE_LOOKUP[normalized]) {
        return BETTING_PRESSURE_RANGE_LOOKUP[normalized];
    }
    for (const [normKey, originalKey] of Object.entries(BETTING_PRESSURE_RANGE_LOOKUP)) {
        if (normalized.includes(normKey)) {
            return originalKey;
        }
    }
    for (const [normKey, originalKey] of Object.entries(BETTING_PRESSURE_RANGE_LOOKUP)) {
        if (normKey.includes(normalized)) {
            return originalKey;
        }
    }
    return null;
}

function getBettingPressureInfo(confidenceLevel, oddsRange, myScore, opponentScore, opponentConfidenceLevel) {
    const normalizedConfidence = normalizeBettingConfidenceLevel(confidenceLevel);
    const matchedRangeKey = resolveBettingOddsRangeKey(oddsRange);
    const rangeRules = matchedRangeKey ? BETTING_PRESSURE_RULES[matchedRangeKey] : null;
    
    let value = rangeRules && normalizedConfidence ? rangeRules[normalizedConfidence] : null;
    
    // 特殊处理：当双方都是信心中庸时，根据分数对比选择使用哪个值
    if (normalizedConfidence === '信心中庸' && typeof value === 'object' && value !== null) {
        const normalizedOpponentConfidence = normalizeBettingConfidenceLevel(opponentConfidenceLevel);
        
        if (normalizedOpponentConfidence === '信心中庸' && typeof myScore === 'number' && typeof opponentScore === 'number') {
            // 双方都是中庸，比较分数
            if (myScore < opponentScore) {
                value = value.lower;  // 我方分数低于对手，使用lower值
            } else if (myScore > opponentScore) {
                value = value.higher; // 我方分数高于对手，使用higher值
            } else {
                value = value.lower;  // 分数相等，默认使用lower
            }
        } else {
            // 对手不是中庸，使用默认值（取lower）
            value = value.lower;
        }
    }
    
    return {
        value: typeof value === 'number' ? value : null,
        normalizedConfidence,
        matchedRangeKey,
        originalConfidence: confidenceLevel || null,
        originalRange: oddsRange || null
    };
}

function renderBettingPressureCell(confidenceLevel, oddsRange, myScore, opponentScore, opponentConfidenceLevel) {
    const info = getBettingPressureInfo(confidenceLevel, oddsRange, myScore, opponentScore, opponentConfidenceLevel);
    if (info.value === null) {
        return '--';
    }
    const tooltipParts = [];
    if (info.originalConfidence) {
        tooltipParts.push(`信心区间: ${info.originalConfidence}`);
    }
    if (info.originalRange) {
        tooltipParts.push(`开盘区间: ${info.originalRange}`);
    }
    if (info.matchedRangeKey && info.originalRange && info.matchedRangeKey !== info.originalRange) {
        tooltipParts.push(`规则匹配: ${info.matchedRangeKey}`);
    } else if (info.matchedRangeKey) {
        tooltipParts.push(`规则匹配: ${info.matchedRangeKey}`);
    }
    const title = tooltipParts.length ? escapeHtmlAttr(tooltipParts.join(' | ')) : '';
    const formatted = formatBettingPressureValue(info.value);
    return title
        ? `<span class="betting-pressure" title="${title}">${formatted}</span>`
        : `<span class="betting-pressure">${formatted}</span>`;
}

function renderInitialConfidenceCell(result) {
    if (!result) {
        return '--';
    }
    const grade = result.grade || '--';
    const tooltipParts = [];
    if (result.zone) {
        tooltipParts.push(`区位: ${result.zone}`);
    }
    if (result.effect && result.effect.length) {
        tooltipParts.push(`作用: ${formatConfidenceEffect(result.effect)}`);
    }
    const title = tooltipParts.length ? escapeHtmlAttr(tooltipParts.join(' | ')) : '';
    return title
        ? `<span class="confidence-grade" title="${title}">${escapeHtml(grade)}</span>`
        : `<span class="confidence-grade">${escapeHtml(grade)}</span>`;
}

function renderCurrentConfidenceCell(result) {
    if (!result) {
        return '--';
    }
    const effect = formatConfidenceEffect(result.effect);
    const tooltipParts = [];
    if (result.zone) {
        tooltipParts.push(`区位: ${result.zone}`);
    }
    if (result.grade) {
        tooltipParts.push(`等级: ${result.grade}`);
    }
    const title = tooltipParts.length ? escapeHtmlAttr(tooltipParts.join(' | ')) : '';
    return title
        ? `<span class="confidence-effect" title="${title}">${escapeHtml(effect)}</span>`
        : `<span class="confidence-effect">${escapeHtml(effect)}</span>`;
}

function getMiddleFlatPositionInfo(band, position) {
    const original = normalizeFlatPositionKey(position);
    const mapped = toMiddleFlatPosition(band, position);
    if (!original && !mapped) {
        return { display: '--', tooltip: '' };
    }
    const display = mapped || original || '--';
    const tooltipParts = [];
    if (band) {
        tooltipParts.push(`信心: ${band}`);
    }
    if (original) {
        tooltipParts.push(`原始: ${original}`);
    }
    if (mapped && original && mapped !== original) {
        tooltipParts.push(`中庸: ${mapped}`);
    }
    return {
        display,
        tooltip: tooltipParts.length ? escapeHtmlAttr(tooltipParts.join(' | ')) : ''
    };
}

function renderMiddlePositionCell(band, position) {
    const info = getMiddleFlatPositionInfo(band, position);
    if (!info || !info.display || info.display === '--') {
        return '--';
    }
    return info.tooltip
        ? `<span class="flat-position" title="${info.tooltip}">${escapeHtml(info.display)}</span>`
        : `<span class="flat-position">${escapeHtml(info.display)}</span>`;
}

function isJsonResponse(response) {
    const contentType = response.headers.get('content-type') || '';
    return contentType.includes('application/json');
}

async function parseJsonResponse(response, contextLabel) {
    if (!response.ok) {
        const payload = await response.text();
        throw new Error(`${contextLabel} request failed with status ${response.status}. Snippet: ${payload.slice(0, 160)}`);
    }
    if (!isJsonResponse(response)) {
        const payload = await response.text();
        throw new Error(`${contextLabel} request did not return JSON. Content-Type: ${response.headers.get('content-type') || 'unknown'}. Snippet: ${payload.slice(0, 160)}`);
    }
    return response.json();
}






// 工具函数
function formatNumber(value, fallback = '--') {
    if (value === null || value === undefined || value === '') {
        return fallback;
    }
    return value;
}

function formatDateTime(dateString) {
    if (!dateString) return '--';
    const date = new Date(dateString);
    const month = (date.getMonth() + 1).toString().padStart(2, '0');
    const day = date.getDate().toString().padStart(2, '0');
    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');
    return `${month}-${day} ${hours}:${minutes}`;
}

function getTeamLogo(teamName) {
    // 生成队徽缩写逻辑
    if (!teamName) return 'FC';
    
    // 特殊队名处理
    const specialNames = {
        '曼城': 'MC',
        '阿森纳': 'ARS',
        '皇家马德里': 'RM',
        '巴塞罗那': 'FCB',
        '拜仁慕尼黑': 'BAY',
        '多特蒙德': 'BVB',
        '利物浦': 'LFC',
        '切尔西': 'CHE',
        '曼联': 'MU',
        '热刺': 'TOT'
    };
    
    if (specialNames[teamName]) {
        return specialNames[teamName];
    }
    
    // 默认取前两个字符或首字母
    const words = teamName.split(' ');
    if (words.length > 1) {
        return words.map(w => w.charAt(0)).join('').substring(0, 3);
    }
    return teamName.substring(0, 2).toUpperCase();
}

function getStatusText(status) {
    const statusMap = {
        'scheduled': '未开始',
        'live': '进行中',
        'finished': '已结束',
        'postponed': '已推迟',
        'cancelled': '已取消'
    };
    return statusMap[status] || status;
}

function getRuleClass(value) {
    const numValue = parseFloat(value);
    if (numValue >= 5) return 'rule-red';      // 5, 5.5 显示红色
    if (numValue >= 4.5) return 'rule-orange'; // 4.5 显示橙色
    if (numValue >= 3.5) return 'rule-yellow'; // 3.5, 4 显示黄色
    if (numValue > 3) return 'rule-yellow';    // 3.5, 4 显示黄色
    return 'rule-green';                       // 小于等于3 显示绿色
}

function getStrengthClass(value) {
    const numValue = parseFloat(value);
    return numValue > 0 ? 'strength-high' : 'strength-low';
}

// ==================== 比赛难度评级相关函数 ====================

// 判断哪支队伍是强队
function getStrongerTeam(company) {
    const homePower = parseFloat(company.homePowerLevel || 0);
    const awayPower = parseFloat(company.awayPowerLevel || 0);
    const diff = (homePower + 1.5) - awayPower;
    
    // diff >= 0 主队是强队，否则客队是强队
    return diff >= 0 ? 'home' : 'away';
}

// 根据规则值判断颜色类型
function getRuleValueColorType(ruleValue) {
    const val = parseFloat(ruleValue);
    if (isNaN(val)) return 'unknown';
    
    if (val <= 3) return 'green';           // 绿色：≤3
    if (val === 3.5 || val === 4) return 'yellow';  // 黄色：只有3.5和4
    if (val === 4.5) return 'orange';       // 橙色：4.5
    if (val >= 5) return 'red';             // 红色：≥5
    
    return 'unknown';
}

// 评估比赛难度并返回星级
function evaluateMatchDifficulty(company) {
    if (!company || !company.initial) {
        return { level: 0, stars: 3, label: '推荐指数' };
    }
    
    // 判断强弱队
    const strongerTeam = getStrongerTeam(company);
    
    // 获取初盘颜色
    const initialHomeColor = getRuleValueColorType(company.initial.homeRuleValue);
    const initialAwayColor = getRuleValueColorType(company.initial.awayRuleValue);
    
    // 确定强队和弱队的颜色
    const strongColor = strongerTeam === 'home' ? initialHomeColor : initialAwayColor;
    const weakColor = strongerTeam === 'home' ? initialAwayColor : initialHomeColor;
    
    // 获取即时盘颜色（如果有）
    let currentStrongColor = null;
    let currentWeakColor = null;
    if (company.current && company.current.homeRuleValue !== undefined && company.current.awayRuleValue !== undefined) {
        const currentHomeColor = getRuleValueColorType(company.current.homeRuleValue);
        const currentAwayColor = getRuleValueColorType(company.current.awayRuleValue);
        currentStrongColor = strongerTeam === 'home' ? currentHomeColor : currentAwayColor;
        currentWeakColor = strongerTeam === 'home' ? currentAwayColor : currentHomeColor;
    }
    
    // 按优先级判断（从最简单到最难）
    
    // 7. 最简单 - 初盘到终盘，强队都是绿色，弱队都是非绿色
    if (currentStrongColor && currentWeakColor &&
        strongColor === 'green' && currentStrongColor === 'green' &&
        weakColor !== 'green' && currentWeakColor !== 'green') {
        return { level: 7, stars: 5, label: '最简单' };
    }
    
    // 6. 更简单 - 初赔强队绿色，弱队黄色
    if (strongColor === 'green' && weakColor === 'yellow') {
        return { level: 6, stars: 5, label: '更简单' };
    }
    
    // 5. 略简单 - 初赔强队绿色，弱队红色
    if (strongColor === 'green' && weakColor === 'red') {
        return { level: 5, stars: 4, label: '略简单' };
    }
    
    // 4. 简单 - 初赔主客双方都是绿色
    if (initialHomeColor === 'green' && initialAwayColor === 'green') {
        return { level: 4, stars: 4, label: '简单' };
    }
    
    // 3. 一般难 - 初赔弱队方向绿色
    if (weakColor === 'green') {
        return { level: 3, stars: 3, label: '一般难' };
    }
    
    // 2. 比较难 - 一方黄色，一方红色
    if ((initialHomeColor === 'yellow' && initialAwayColor === 'red') ||
        (initialHomeColor === 'red' && initialAwayColor === 'yellow')) {
        return { level: 2, stars: 2, label: '比较难' };
    }
    
    // 1. 最难 - 主客双方均是黄色
    if (initialHomeColor === 'yellow' && initialAwayColor === 'yellow') {
        return { level: 1, stars: 1, label: '最难' };
    }
    
    // 默认 - 不在规则内，显示3星
    return { level: 0, stars: 3, label: '推荐指数' };
}

// 生成星级HTML（空心+实心）
function generateStarsHTML(stars) {
    const maxStars = 5;
    let html = '';
    
    for (let i = 1; i <= maxStars; i++) {
        if (i <= stars) {
            html += '⭐'; // 实心星星
        } else {
            html += '☆';  // 空心星星
        }
    }
    
    return html;
}

function translateRecommendation(recommendation) {
    if (!recommendation) return '--';
    const map = {
        'home': '主胜',
        'draw': '平局', 
        'away': '客胜',
        '3': '主胜',
        '1': '平局',
        '0': '客胜'
    };
    return map[recommendation] || recommendation;
}

// API请求函数
async function fetchMatches(statusParam = '') {
    try {
        const timestamp = Date.now();
        // 构建URL，如果有status参数则添加
        let url = `/api/public/matches/today?_t=${timestamp}`;
        if (statusParam) {
            url += `&status=${statusParam}`;
        }
        
        // 直接使用公共API，避免认证延迟
        const response = await fetch(url, {
            cache: 'no-cache',
            headers: {
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache'
            }
        });

        const data = await parseJsonResponse(response, 'Match list');

        if (data.success) {
            allMatches = data.data || [];
            renderMatchesList();
            updateFilters();
            updateLastUpdateTime();
        } else {
            console.error('Failed to fetch match list:', data.error);
            showError('Failed to fetch match data.');
        }
    } catch (error) {
        console.error('Request failed:', error);
        showError('Network request failed, please refresh the page or log in again.');
    }
}



async function fetchMatchDetail(matchId) {
    try {
        showDetailLoading();
        const timestamp = Date.now();
        // 直接使用公共API，避免认证延迟
        const response = await fetch(`/api/public/matches/${matchId}?_t=${timestamp}`, {
            cache: 'no-cache',
            headers: {
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache'
            }
        });

        const data = await parseJsonResponse(response, 'Match detail');

        if (data.success) {
            renderMatchDetail(data.data);

            const hasPoisson = Boolean(data.data && data.data.poissonPrediction);
            if (!hasPoisson) {
                try {
                    const fallbackResponse = await fetch(`/api/public/matches/${matchId}?_t=${timestamp}`, {
                        cache: 'no-cache'
                    });
                    if (fallbackResponse.ok && isJsonResponse(fallbackResponse)) {
                        const fallbackJson = await fallbackResponse.json();
                        if (fallbackJson && fallbackJson.success && fallbackJson.data && fallbackJson.data.poissonPrediction) {
                            window.currentMatchData = window.currentMatchData || {};
                            window.currentMatchData.poissonPrediction = fallbackJson.data.poissonPrediction;

                            const container = document.getElementById('poisson-analysis-container');
                            const btn = document.getElementById('view-poisson-btn');
                            if (container && btn) {
                                container.style.display = 'block';
                                btn.disabled = false;
                                btn.textContent = '查看泊松分布预测';
                                btn.title = '';
                            }

                            updatePoissonModal(fallbackJson.data.poissonPrediction);
                            // [新增] 显示大小3球快速预览
                            updateQuickOU3Preview(fallbackJson.data.poissonPrediction);
                        }
                    }
                } catch (fallbackError) {
                    console.warn('Fallback public detail fetch failed:', fallbackError);
                }
            }
        } else {
            console.error('Failed to fetch match detail:', data.error);
            showError('Failed to fetch match detail.');
        }
    } catch (error) {
        console.error('Request failed while fetching match detail:', error);
        showError('Network request failed.');
    }
}



// 渲染函数
function renderMatchesList() {
    const container = document.getElementById('matchesList');
    const leagueFilter = document.getElementById('leagueFilter').value;
    const dateFilter = document.getElementById('dateFilter').value;
    const statusFilter = document.getElementById('statusFilter').value;
    const customDate = document.getElementById('customDate').value;
    
    // 过滤比赛
    let filteredMatches = allMatches;
    
    if (leagueFilter) {
        filteredMatches = filteredMatches.filter(m => m.leagueId == leagueFilter);
    }
    
    if (statusFilter) {
        filteredMatches = filteredMatches.filter(m => m.matchStatus === statusFilter);
    }
    
    if (dateFilter && !customDate) {
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const tomorrow = new Date(today);
        tomorrow.setDate(tomorrow.getDate() + 1);
        const nextWeek = new Date(today);
        nextWeek.setDate(nextWeek.getDate() + 7);
        
        filteredMatches = filteredMatches.filter(m => {
            const matchDate = new Date(m.matchTime);
            switch (dateFilter) {
                case 'today':
                    return matchDate >= today && matchDate < tomorrow;
                case 'tomorrow':
                    return matchDate >= tomorrow && matchDate < new Date(tomorrow.getTime() + 24*60*60*1000);
                case 'week':
                    return matchDate >= today && matchDate < nextWeek;
                default:
                    return true;
            }
        });
    }
    
    if (customDate) {
        const selectedDate = new Date(customDate);
        const nextDay = new Date(selectedDate);
        nextDay.setDate(selectedDate.getDate() + 1);
        
        filteredMatches = filteredMatches.filter(m => {
            const matchDate = new Date(m.matchTime);
            return matchDate >= selectedDate && matchDate < nextDay;
        });
    }
    
    // 渲染列表
    if (filteredMatches.length === 0) {
        container.innerHTML = '<div class="loading">暂无比赛数据</div>';
        return;
    }
    
    container.innerHTML = filteredMatches.map(match => {
        return `
            <div class="match-card" onclick="showDetail(${match.matchId})">
                <div class="match-header">
                    <div class="match-time">${formatDateTime(match.matchTime)}</div>
                    <div class="league-name">${match.leagueName || '未知联赛'}</div>
                </div>
                
                <div class="teams-section">
                    <div class="team">
                        <div class="team-logo">${getTeamLogo(match.homeTeam)}</div>
                        <div class="team-info">
                            <div class="team-name">${match.homeTeam || '主队'}</div>
                        </div>
                    </div>
                    <div class="vs-divider">VS</div>
                    <div class="team">
                        <div class="team-logo">${getTeamLogo(match.awayTeam)}</div>
                        <div class="team-info">
                            <div class="team-name">${match.awayTeam || '客队'}</div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

function renderLoginPrompt() {
    const detailContent = document.getElementById('detailContent');
    const matchCard = document.getElementById('detailMatchCard');
    
    // 清空比赛基本信息卡片
    matchCard.innerHTML = '';

    detailContent.innerHTML = `
        <div class="detail-card">
             <h3 style="color: #FF9800;">需要登录</h3>
             <div class="loading" style="text-align: center; padding: 2rem;">
                 <p style="margin-bottom: 1.5rem; font-size: 1.1rem; color: #eee;">
                    您需要登录后才能查看详细的比赛分析数据。
                 </p>
                 <a href="/login" style="display: inline-block; padding: 0.8rem 2rem; background-color: #32CD32; color: white; text-decoration: none; border-radius: 8px; font-weight: bold; transition: background-color 0.3s ease;">
                     前往登录
                 </a>
             </div>
        </div>
    `;
}

async function renderMatchDetail(match) {
    // 保存当前比赛数据到全局变量
    window.currentMatchData = match;
    
    // [性能优化] 存储所有公司的数据，以便按需加载
    // 初始只显示前10个公司，点击"加载全部"后显示所有公司
    const allCompanies = match.companyAnalyses || [];
    const initialLoadCount = 10; // 初始加载数量
    
    window.fullCompanyAnalyses = allCompanies; // 保存完整的公司列表
    window.allCompanyAnalyses = allCompanies.slice(0, initialLoadCount); // 初始显示前N个
    window.totalCompanyCount = allCompanies.length; // 总数为全部公司数量
    
    console.log(`赔率分析公司: 初始加载 ${window.allCompanyAnalyses.length} 家，总共 ${window.totalCompanyCount} 家`);

    // 渲染比赛基本信息
    const matchCard = document.getElementById('detailMatchCard');
    
    // 计算推荐指数（基于主要公司数据）
    let difficultyInfo = { level: 0, stars: 3, label: '推荐指数' };
    if (match.companyAnalyses && match.companyAnalyses.length > 0) {
        // 优先使用澳门(80)，没有就用威廉希尔(115)，都没有就用第一个有效公司
        const macau = match.companyAnalyses.find(c => c.companyId == 80);
        const william = match.companyAnalyses.find(c => c.companyId == 115);
        
        let mainCompany = null;
        if (macau && macau.initial && macau.initial.homeRange) {
            mainCompany = macau;
        } else if (william && william.initial && william.initial.homeRange) {
            mainCompany = william;
        } else {
            mainCompany = match.companyAnalyses.find(c => c.initial && c.initial.homeRange) || match.companyAnalyses[0];
        }
        
        if (mainCompany) {
            difficultyInfo = evaluateMatchDifficulty(mainCompany);
        }
    }
    
    matchCard.innerHTML = `
        <div class="match-header">
            <div class="match-time">${formatDateTime(match.matchTime)}</div>
            <div class="league-name">
                ${match.leagueName || '未知联赛'}
                ${match.roundNumber && match.totalRounds ? 
                    `<span style="margin-left: 10px; color: #ff6b6b; font-weight: 600;">第${match.roundNumber}/${match.totalRounds}轮</span>` : 
                    ''}
            </div>
        </div>
        
        <div class="teams-section">
            <div class="team">
                <div class="team-logo">${match.homeTeamLogo || getTeamLogo(match.homeTeam)}</div>
                <div class="team-info">
                    <div class="team-name">
                        ${match.homeTeam || '主队'} 
                        ${match.standings && match.standings.home ? `<span style="color: #ff6b6b; font-size: 0.9em; margin-left: 5px; font-weight: 600;">[${match.standings.home.position}名]</span>` : ''}
                    </div>
                </div>
            </div>
            <div class="recommendation-indicator">
                ${match.matchStatus === 'finished' || match.matchStatus === 'live' ? 
                    `<div style="font-size: 1.5rem; font-weight: bold; color: #fff;">${formatNumber(match.homeScore, 0)} - ${formatNumber(match.awayScore, 0)}</div>` : 
                    `<div style="text-align: center;">
                        <div style="font-size: 0.85rem; color: #999; margin-bottom: 0.3rem;">${difficultyInfo.label}</div>
                        <div style="font-size: 1.8rem; letter-spacing: 2px;">${generateStarsHTML(difficultyInfo.stars)}</div>
                        ${difficultyInfo.level > 0 ? `<div style="font-size: 0.75rem; color: #ffa726; margin-top: 0.2rem;">${difficultyInfo.label}</div>` : ''}
                    </div>`
                }
            </div>
            <div class="team">
                <div class="team-logo">${match.awayTeamLogo || getTeamLogo(match.awayTeam)}</div>
                <div class="team-info">
                    <div class="team-name">
                        ${match.awayTeam || '客队'}
                        ${match.standings && match.standings.away ? `<span style="color: #ff6b6b; font-size: 0.9em; margin-left: 5px; font-weight: 600;">[${match.standings.away.position}名]</span>` : ''}
                    </div>
                </div>
            </div>
        </div>
        
        ${generateOddsCard(match)}
    `;
    
    // 渲染详细分析
    const detailContent = document.getElementById('detailContent');
    let html = '';
    
    // 不再显示单独的积分榜信息栏，排名已经在队名旁边显示了
    
    
    // 基本面分析
    if (match.fundamentalAnalysis) {
        const fa = match.fundamentalAnalysis;
        
        // 获取主公司的初盘数据用于受注力计算
        // [修正] 优先寻找澳门(80)，没有就用威廉希尔(115)，都没有就用第一个有效公司
        let mainCompany = null;
        if (match.companyAnalyses && match.companyAnalyses.length > 0) {
            // 1. 尝试寻找澳门 (ID: 80)
            const macau = match.companyAnalyses.find(c => c.companyId == 80);
            // 2. 尝试寻找威廉希尔 (ID: 115)
            const william = match.companyAnalyses.find(c => c.companyId == 115);
            
            // 3. 检查数据是否有效 (检查 initial 和 homeRange)
            if (macau && macau.initial && macau.initial.homeRange) {
                mainCompany = macau;
            } else if (william && william.initial && william.initial.homeRange) {
                mainCompany = william;
            } else {
                // 4. 如果都没有，则寻找列表中第一个有有效初盘数据的公司
                mainCompany = match.companyAnalyses.find(c => c.initial && c.initial.homeRange) || null;
            }
        }
        
        
        html += `
            <div class="detail-card">
                <h3>基本面分析</h3>
                
                <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 1.5rem; margin-top: 1.5rem;">
                    <!-- 主队分析卡片 -->
                    <div style="background: linear-gradient(135deg, rgba(16, 185, 129, 0.1), rgba(5, 150, 105, 0.15)); 
                                border-left: 4px solid #10b981; border-radius: 12px; padding: 1.5rem;">
                        <h4 style="color: #10b981; margin: 0 0 1rem 0; font-size: 1.1rem; font-weight: 700; display: flex; align-items: center; justify-content: space-between;">
                            主队分析
                            ${fa.homeWin && fa.homeWin.oddsSuggestions ? '<button onclick="toggleHomeRange(event)" onmouseover="this.style.background=\'rgba(16, 185, 129, 0.35)\'" onmouseout="this.style.background=\'rgba(16, 185, 129, 0.2)\'" style="background: rgba(16, 185, 129, 0.2); border: none; color: #10b981; padding: 0.3rem 0.6rem; border-radius: 6px; cursor: pointer; font-size: 0.8rem; font-weight: 600; transition: all 0.2s ease;">显示区间 ▼</button>' : ''}
                        </h4>
                        ${fa.homeWin ? `
                            <div style="margin-bottom: 1rem;">
                                <div style="color: #64748b; font-size: 0.85rem; margin-bottom: 0.3rem;">信心区间</div>
                                <div style="font-size: ${fa.homeWin.score ? '2.2rem' : '1.5rem'}; font-weight: 700; color: #10b981; line-height: 1;">
                                    ${fa.homeWin.score ? fa.homeWin.score.toFixed(1) : ''}
                                </div>
                                <div style="font-size: 0.9rem; color: #059669; margin-top: 0.3rem; font-weight: 600;">
                                    ${fa.homeWin.confidenceLevel || '--'}
                                </div>
                            </div>
                            <div id="home-range-detail" style="display: none; padding-top: 1rem; border-top: 1px solid rgba(16, 185, 129, 0.2);">
                                <div style="color: #64748b; font-size: 0.85rem; margin-bottom: 0.3rem;">合理开盘区间</div>
                                <div style="font-size: 1rem; color: #1e293b; font-weight: 600;">
                                    ${fa.homeWin.oddsSuggestions || '--'}
                                </div>
                            </div>
                        ` : '<div style="color: #64748b; text-align: center;">暂无数据</div>'}
                    </div>

                    <!-- 平局分析卡片 -->
                    <div style="background: linear-gradient(135deg, rgba(245, 158, 11, 0.1), rgba(217, 119, 6, 0.15)); 
                                border-left: 4px solid #f59e0b; border-radius: 12px; padding: 1.5rem;">
                        <h4 style="color: #f59e0b; margin: 0 0 1rem 0; font-size: 1.1rem; font-weight: 700;">平局分析</h4>
                        ${fa.draw ? `
                            <div style="margin-bottom: 1rem;">
                                <div style="color: #64748b; font-size: 0.85rem; margin-bottom: 0.3rem;">信心区间</div>
                                <div style="font-size: ${fa.draw.score ? '2.2rem' : '1.5rem'}; font-weight: 700; color: #f59e0b; line-height: 1;">
                                    ${fa.draw.score ? fa.draw.score.toFixed(1) : ''}
                                </div>
                                <div style="font-size: 0.9rem; color: #d97706; margin-top: 0.3rem; font-weight: 600;">
                                    ${fa.draw.confidenceLevel || '--'}
                                </div>
                            </div>
                        ` : '<div style="color: #64748b; text-align: center;">暂无数据</div>'}
                    </div>

                    <!-- 客队分析卡片 -->
                    <div style="background: linear-gradient(135deg, rgba(239, 68, 68, 0.1), rgba(220, 38, 38, 0.15)); 
                                border-left: 4px solid #ef4444; border-radius: 12px; padding: 1.5rem;">
                        <h4 style="color: #ef4444; margin: 0 0 1rem 0; font-size: 1.1rem; font-weight: 700; display: flex; align-items: center; justify-content: space-between;">
                            客队分析
                            ${fa.awayWin && fa.awayWin.oddsSuggestions ? '<button onclick="toggleAwayRange(event)" onmouseover="this.style.background=\'rgba(239, 68, 68, 0.35)\'" onmouseout="this.style.background=\'rgba(239, 68, 68, 0.2)\'" style="background: rgba(239, 68, 68, 0.2); border: none; color: #ef4444; padding: 0.3rem 0.6rem; border-radius: 6px; cursor: pointer; font-size: 0.8rem; font-weight: 600; transition: all 0.2s ease;">显示区间 ▼</button>' : ''}
                        </h4>
                        ${fa.awayWin ? `
                            <div style="margin-bottom: 1rem;">
                                <div style="color: #64748b; font-size: 0.85rem; margin-bottom: 0.3rem;">信心区间</div>
                                <div style="font-size: ${fa.awayWin.score ? '2.2rem' : '1.5rem'}; font-weight: 700; color: #ef4444; line-height: 1;">
                                    ${fa.awayWin.score ? fa.awayWin.score.toFixed(1) : ''}
                                </div>
                                <div style="font-size: 0.9rem; color: #dc2626; margin-top: 0.3rem; font-weight: 600;">
                                    ${fa.awayWin.confidenceLevel || '--'}
                                </div>
                            </div>
                            <div id="away-range-detail" style="display: none; padding-top: 1rem; border-top: 1px solid rgba(239, 68, 68, 0.2);">
                                <div style="color: #64748b; font-size: 0.85rem; margin-bottom: 0.3rem;">合理开盘区间</div>
                                <div style="font-size: 1rem; color: #1e293b; font-weight: 600;">
                                    ${fa.awayWin.oddsSuggestions || '--'}
                                </div>
                            </div>
                        ` : '<div style="color: #64748b; text-align: center;">暂无数据</div>'}
                    </div>
                </div>
            </div>
        `;

        // 临场基本面分析卡片（拉力方向 + 缺阵 + 赛事提示）
        const hasPrompts = fa.prompts && fa.prompts.length > 0;
        const hasAbsent = fa.absentPlayers && (
            (fa.absentPlayers.home && fa.absentPlayers.home.length > 0) ||
            (fa.absentPlayers.away && fa.absentPlayers.away.length > 0)
        );

        if (fa.pullDirection || fa.distributionNode || hasPrompts || hasAbsent) {
            html += `
            <div class="detail-card">
                <h3>临场基本面分析</h3>
            `;

            // 拉力方向指示条
            if (fa.pullDirection) {
                const pullColors = {
                    home: { bg: 'rgba(16, 185, 129, 0.15)', border: '#10b981', text: '#059669', icon: '← 主' },
                    away: { bg: 'rgba(239, 68, 68, 0.15)', border: '#ef4444', text: '#dc2626', icon: '客 →' },
                    draw: { bg: 'rgba(245, 158, 11, 0.15)', border: '#f59e0b', text: '#d97706', icon: '⇔ 平' },
                    balanced: { bg: 'rgba(100, 116, 139, 0.15)', border: '#94a3b8', text: '#64748b', icon: '= 均衡' },
                };
                const pc = pullColors[fa.pullDirection] || pullColors.balanced;
                html += `
                <div style="background: ${pc.bg}; border-left: 4px solid ${pc.border}; border-radius: 8px; padding: 1rem 1.2rem; margin-bottom: 1.2rem; display: flex; align-items: center; gap: 1rem;">
                    <div style="font-size: 1.5rem; font-weight: 800; color: ${pc.text}; min-width: 3.5rem; text-align: center;">${pc.icon}</div>
                    <div>
                        <div style="font-size: 1rem; font-weight: 700; color: ${pc.text};">拉力方向：${fa.pullDescription || fa.pullDirection}</div>
                        <div style="font-size: 0.8rem; color: #94a3b8; margin-top: 0.2rem;">基于胜率、赢盘率、历史交锋综合计算</div>
                    </div>
                </div>
                `;
            }

            // 分布判断（试行）
            if (fa.distributionNode) {
                html += `
                <div style="background: rgba(99,102,241,0.07); border-left: 4px solid #6366f1; border-radius: 8px; padding: 0.75rem 1.2rem; margin-bottom: 1.2rem; display: flex; align-items: center; gap: 0.6rem;">
                    <span style="font-size: 0.85rem; color: #64748b; flex-shrink: 0;">分布判断（试行）：</span>
                    <span style="font-size: 1rem; font-weight: 700; color: #4f46e5;">${fa.distributionNode}</span>
                </div>
                `;
            }

            // 赛事提示标签（缺阵信息不在标签区展示，在下方列表单独显示）
            const nonAbsentPrompts = (fa.prompts || []).filter(p => !p.includes('缺阵'));
            if (nonAbsentPrompts.length > 0) {
                html += '<div style="display: flex; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 1.2rem;">';
                nonAbsentPrompts.forEach(p => {
                    let tagStyle = 'background: rgba(100,116,139,0.12); color: #64748b; border: 1px solid rgba(100,116,139,0.2);';
                    if (p.includes('赛程密集')) tagStyle = 'background: rgba(245,158,11,0.1); color: #d97706; border: 1px solid rgba(245,158,11,0.2);';
                    else if (p.includes('长休息')) tagStyle = 'background: rgba(99,102,241,0.1); color: #6366f1; border: 1px solid rgba(99,102,241,0.2);';
                    else if (p.includes('连胜')) tagStyle = 'background: rgba(16,185,129,0.1); color: #059669; border: 1px solid rgba(16,185,129,0.2);';
                    else if (p.includes('连败')) tagStyle = 'background: rgba(59,130,246,0.1); color: #3b82f6; border: 1px solid rgba(59,130,246,0.2);';
                    else if (p.includes('德比') || p.includes('国家德比')) tagStyle = 'background: rgba(234,179,8,0.15); color: #b45309; border: 1px solid rgba(234,179,8,0.3);';
                    else if (p.includes('保级')) tagStyle = 'background: rgba(239,68,68,0.12); color: #b91c1c; border: 1px solid rgba(239,68,68,0.25);';
                    else if (p.includes('争冠')) tagStyle = 'background: rgba(234,179,8,0.12); color: #92400e; border: 1px solid rgba(234,179,8,0.25);';
                    else if (p.includes('血脉压制')) tagStyle = 'background: rgba(220,38,38,0.15); color: #991b1b; border: 1px solid rgba(220,38,38,0.3);';
                    else if (p.includes('在即')) tagStyle = 'background: rgba(124,58,237,0.12); color: #6d28d9; border: 1px solid rgba(124,58,237,0.25);';
                    else if (p.includes('复仇')) tagStyle = 'background: rgba(168,85,247,0.1); color: #7c3aed; border: 1px solid rgba(168,85,247,0.2);';
                    else if (p.includes('历史')) tagStyle = 'background: rgba(168,85,247,0.08); color: #7c3aed; border: 1px solid rgba(168,85,247,0.15);';
                    html += '<span style="' + tagStyle + ' padding: 0.3rem 0.7rem; border-radius: 6px; font-size: 0.8rem; font-weight: 500; white-space: nowrap;">' + p + '</span>';
                });
                html += '</div>';
            }

            // 缺阵信息面板
            if (hasAbsent) {
                const homeAbs = fa.absentPlayers.home || [];
                const awayAbs = fa.absentPlayers.away || [];
                html += `
                <div style="margin-top: 0.5rem;">
                    <div style="font-size: 0.9rem; font-weight: 700; color: #1e293b; margin-bottom: 0.8rem;">缺阵信息</div>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
                        <div style="background: rgba(239,68,68,0.05); border-radius: 8px; padding: 0.8rem;">
                            <div style="font-size: 0.8rem; font-weight: 600; color: #ef4444; margin-bottom: 0.5rem;">
                                ${match.homeTeamNameCn || match.homeTeamName || '主队'} (${homeAbs.length})
                            </div>
                            ${homeAbs.length > 0
                                ? homeAbs.map(p => '<div style="font-size: 0.78rem; color: #64748b; padding: 0.15rem 0; border-bottom: 1px solid rgba(0,0,0,0.04);">' + p + '</div>').join('')
                                : '<div style="font-size: 0.78rem; color: #94a3b8;">暂无缺阵信息</div>'}
                        </div>
                        <div style="background: rgba(239,68,68,0.05); border-radius: 8px; padding: 0.8rem;">
                            <div style="font-size: 0.8rem; font-weight: 600; color: #ef4444; margin-bottom: 0.5rem;">
                                ${match.awayTeamNameCn || match.awayTeamName || '客队'} (${awayAbs.length})
                            </div>
                            ${awayAbs.length > 0
                                ? awayAbs.map(p => '<div style="font-size: 0.78rem; color: #64748b; padding: 0.15rem 0; border-bottom: 1px solid rgba(0,0,0,0.04);">' + p + '</div>').join('')
                                : '<div style="font-size: 0.78rem; color: #94a3b8;">暂无缺阵信息</div>'}
                        </div>
                    </div>
                </div>
                `;
            }

            // 赛前简报
            if (fa.briefing) {
                html += `
                <div style="margin-top: 1.2rem; background: rgba(59,130,246,0.05); border-radius: 8px; padding: 1rem;">
                    <div style="font-size: 0.9rem; font-weight: 700; color: #1e293b; margin-bottom: 0.5rem;">赛前简报</div>
                    <div style="font-size: 0.82rem; color: #475569; line-height: 1.7;">${fa.briefing}</div>
                </div>
                `;
            }

            html += '</div>';
        }

    } else {
        html += `
            <div class="detail-card">
                <h3>基本面分析</h3>
                <div class="loading">暂无基本面分析数据</div>
            </div>
        `;
    }
    
    // 长节点控赔分析（兼容 camelCase / snake_case）
    const drawSys = match.drawSystemAnalysis || match.draw_system_analysis;
    if (drawSys) {
        html += renderDrawSystemCard(drawSys);
    }

    // 赔率分析
    if (window.allCompanyAnalyses && window.allCompanyAnalyses.length > 0) {
        const companies = window.allCompanyAnalyses; // 使用过滤后的公司列表
        const mainCompany = companies[0]; // 默认显示第一个公司
        
        html += `
            <div class="detail-card">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                    <h3 style="margin: 0;">赔率分析</h3>
                    <div class="company-selector">
                        <select class="company-select" id="companySelect" onchange="updateOddsTable()">
                            ${companies.map((company, index) => 
                                `<option value="${company.companyId}">${company.companyName || '未知公司'}</option>`
                            ).join('')}
                        </select>
                    </div>
                </div>

                <div id="loadMoreContainer" class="load-more-container">
                    <!-- 按需加载按钮将在这里动态生成 -->
                </div>

                <table class="odds-table">
                    <thead>
                        <tr>
                            <th>盘口类型</th>
                            <th>主队广义实力</th>
                            <th>主队开盘区间</th>
                            <th>主队受注/作用</th>
                            <th>平赔区间</th>
                            <th>客队广义实力</th>
                            <th>客队开盘区间</th>
                            <th>客队受注/作用</th>
                            <th>规则差值</th>
                            <th>首选推荐</th>
                        </tr>
                    </thead>
                    <tbody id="oddsTableBody">
                        ${generateOddsTableRows(mainCompany)}
                    </tbody>
                </table>

                ${generateCompanySummary(match)}
            </div>
        `;
    } else {
        html += `
            <div class="detail-card">
                <h3>赔率分析</h3>
                <div class="loading">暂无赔率分析数据</div>
            </div>
        `;
    }
    
    // [新增] 大小3球快速预览 - 增强视觉对比
    html += `
        <div id="quick-ou3-preview" class="detail-card" style="display: none; grid-column: 1 / -1; background: linear-gradient(135deg, rgba(102, 126, 234, 0.08) 0%, rgba(118, 75, 162, 0.08) 100%); border: 1px solid rgba(102, 126, 234, 0.3);">
            <h3 style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 1.5rem; font-size: 1.2rem; font-weight: 700;">
                <span style="font-size: 1.3rem;">⚽</span>
                大小3球预测
                <span id="quick-ou3-method" style="font-size: 0.75rem; background: rgba(102, 126, 234, 0.15); padding: 0.3rem 0.8rem; border-radius: 12px; font-weight: 600; margin-left: auto;">--</span>
            </h3>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem;">
                <div id="quick-ou3-over-card" style="background: linear-gradient(135deg, rgba(239, 68, 68, 0.15) 0%, rgba(220, 38, 38, 0.2) 100%); 
                            padding: 2rem 1.5rem; border-radius: 16px; border: 2.5px solid #ef4444; text-align: center;
                            box-shadow: 0 4px 20px rgba(239, 68, 68, 0.25); transition: all 0.3s ease;">
                    <div style="font-size: 0.9rem; color: #1e293b; margin-bottom: 0.8rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em;">大于3球 (>3球)</div>
                    <div id="quick-ou3-over" style="font-size: 3rem; font-weight: 800; color: #ef4444; line-height: 1; letter-spacing: -0.02em;">--%</div>
                </div>
                <div id="quick-ou3-under-card" style="background: linear-gradient(135deg, rgba(59, 130, 246, 0.15) 0%, rgba(37, 99, 235, 0.2) 100%); 
                            padding: 2rem 1.5rem; border-radius: 16px; border: 2.5px solid #3b82f6; text-align: center;
                            box-shadow: 0 4px 20px rgba(59, 130, 246, 0.25); transition: all 0.3s ease;">
                    <div style="font-size: 0.9rem; color: #1e293b; margin-bottom: 0.8rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em;">小于等于3球 (≤3球)</div>
                    <div id="quick-ou3-under" style="font-size: 3rem; font-weight: 800; color: #3b82f6; line-height: 1; letter-spacing: -0.02em;">--%</div>
                </div>
            </div>
        </div>
    `;
    
    // [新增] 泊松分析按钮容器 - 使用grid-column让它跨越整行，不破坏双列布局
    html += `
        <div id="poisson-analysis-container" class="mt-4" style="display: none; grid-column: 1 / -1;">
            <button id="view-poisson-btn" class="back-btn" style="width: 100%; margin-bottom: 0;">查看泊松分布预测</button>
        </div>
    `;
    
    detailContent.innerHTML = html;
    
    // [新增] 绑定泊松按钮事件
    const poissonBtn = document.getElementById('view-poisson-btn');
    if (poissonBtn) {
        poissonBtn.addEventListener('click', () => {
            document.getElementById('poisson-modal').style.display = 'block';
            document.getElementById('poisson-modal-backdrop').style.display = 'block';
        });
    }
    
    // [性能优化] 渲染"加载更多"按钮
    renderLoadMoreButton();

    // 存储当前比赛数据供其他函数使用
    window.currentMatchData = match;

    // 更新泊松分布预测（最小集成：优先受保护接口；无则显示"获取中"并尝试公共接口）
    const poissonContainer = document.getElementById('poisson-analysis-container');
    if (poissonContainer && poissonBtn) {
        poissonContainer.style.display = 'block';
        if (match.poissonPrediction && (match.poissonPrediction.prediction || match.poissonPrediction.expected_goals)) {
            updatePoissonModal(match.poissonPrediction);
            poissonBtn.disabled = false;
            poissonBtn.textContent = '查看泊松分布预测';
            poissonBtn.title = '';
            
            // [新增] 显示大小3球快速预览
            updateQuickOU3Preview(match.poissonPrediction);
        } else if (match.poissonPrediction && match.poissonPrediction.error) {
            poissonBtn.disabled = true;
            poissonBtn.textContent = '无法生成泊松预测';
            poissonBtn.title = match.poissonPrediction.error;
        } else {
            // 无受保护数据，先占位为"获取中"，后续公共接口兜底会刷新
            poissonBtn.disabled = true;
            poissonBtn.textContent = '获取泊松预测中…';
            poissonBtn.title = '';
        }
    }
}

/**
 * 更新大小3球快速预览
 * @param {object} data 泊松预测数据
 */
function updateQuickOU3Preview(data) {
    const preview = document.getElementById('quick-ou3-preview');
    if (!preview) return;
    
    const prediction = (data && data.prediction) ? data.prediction : data;
    const totalGoalsProbs = prediction?.total_goals_probs || data?.total_goals_probs || {};
    
    // 获取概率：大于3球(>3) 和 小于等于3球(≤3)
    const le3 = totalGoalsProbs.le3 || 0;  // ≤3球
    const gt3 = totalGoalsProbs.gt3 || 0;  // >3球
    
    // 显示数据
    const overEl = document.getElementById('quick-ou3-over');
    const underEl = document.getElementById('quick-ou3-under');
    const overCard = document.getElementById('quick-ou3-over-card');
    const underCard = document.getElementById('quick-ou3-under-card');
    const eq3El = document.getElementById('quick-ou3-eq3');
    const methodEl = document.getElementById('quick-ou3-method');
    
    if (overEl) overEl.textContent = gt3 ? `${Math.round(gt3)}%` : '--%';
    if (underEl) underEl.textContent = le3 ? `${Math.round(le3)}%` : '--%';
    if (eq3El) eq3El.style.display = 'none';  // 隐藏等于3球的显示
    
    // 为优势方添加脉冲动画
    if (gt3 && le3) {
        if (gt3 > le3 && overCard) {
            overCard.style.animation = 'pulse-glow-red 2s infinite';
        } else if (le3 > gt3 && underCard) {
            underCard.style.animation = 'pulse-glow-blue 2s infinite';
        }
    }
    
    // 方法标识
    const method = prediction?.method || data?.method || 'Poisson';
    if (methodEl) {
        if (method.includes('Bivariate')) {
            methodEl.textContent = '🔗 双变量';
        } else if (method.includes('Dixon')) {
            methodEl.textContent = '🔬 DC修正';
        } else {
            methodEl.textContent = '📊 泊松';
        }
    }
    
    // 显示卡片
    preview.style.display = 'block';
}

/**
 * 更新泊松分布模态框内容
 * @param {object} data 预测数据
 */
function updatePoissonModal(data) {
    // 兼容两种结构：
    // A) { prediction: { expected_goals, over_under, ... }, match_info: {...} }
    // B) { expected_goals, over_under, ... }
    const prediction = (data && data.prediction) ? data.prediction : data;
    const matchInfo = data?.match_info;

    // 取融合后的指标（若存在），否则回退传统值
    const fusion = data?.fusion || prediction?.fusion;
    const egFusion = fusion && (typeof fusion.home_final === 'number') && (typeof fusion.away_final === 'number')
        ? { home: fusion.home_final, away: fusion.away_final, total: (fusion.home_final + fusion.away_final) }
        : null;
    const expectedGoals = egFusion || prediction?.expected_goals || {};

    // 更新标题
    const titleEl = document.getElementById('poisson-modal-title');
    if (titleEl) {
        titleEl.textContent = (matchInfo?.home_team && matchInfo?.away_team)
            ? `${matchInfo.home_team} vs ${matchInfo.away_team} - 泊松分布预测`
            : '泊松分布预测';
    }

    // 更新预期进球
    document.getElementById('poisson-expected-home-goals').textContent = expectedGoals?.home ?? '--';
    document.getElementById('poisson-expected-away-goals').textContent = expectedGoals?.away ?? '--';
    document.getElementById('poisson-expected-total-goals').textContent = expectedGoals?.total ?? '--';

    // 更新比赛结果概率
    document.getElementById('poisson-home-win-prob').textContent = `${prediction?.outcomes?.home_win ?? '--'}%`;
    document.getElementById('poisson-draw-prob').textContent = `${prediction?.outcomes?.draw ?? '--'}%`;
    document.getElementById('poisson-away-win-prob').textContent = `${prediction?.outcomes?.away_win ?? '--'}%`;

    // 更新最可能比分
    const mostLikely = prediction?.most_likely;
    const mostLikelyEl = document.getElementById('poisson-most-likely-score');
    if (mostLikelyEl) {
        mostLikelyEl.textContent = mostLikely
            ? `${mostLikely.score} (${mostLikely.percentage}%)`
            : '--';
    }

    // 更新大小球概率（按融合/传统就近取值）
    const overUnderEl = document.getElementById('poisson-over-under-list');
    if (overUnderEl) {
        const overUnder = prediction?.over_under || data?.over_under;
        if (overUnder) {
            const overUnderContent = Object.entries(overUnder)
                .filter(([key, _]) => !key.endsWith('_odds'))
                .map(([key, value]) => `<li>${key}: <strong>${value ?? '--'}%</strong></li>`)
                .join('');
            overUnderEl.innerHTML = overUnderContent;
        } else {
            overUnderEl.innerHTML = '<li>--</li>';
        }
    }

    // [增强] 更新总进球分布 (P(S≤3), P(S>3))
    const totalGoalsProbs = prediction?.total_goals_probs || data?.total_goals_probs || {};
    const sLe3El = document.getElementById('poisson-s-le3') || document.getElementById('poisson-s-le2');
    const sGt3El = document.getElementById('poisson-s-gt3') || document.getElementById('poisson-s-ge4');
    const sEq3El = document.getElementById('poisson-s-eq3');
    
    if (sLe3El) sLe3El.textContent = totalGoalsProbs.le3 ? `${totalGoalsProbs.le3}%` : '--';
    if (sGt3El) sGt3El.textContent = totalGoalsProbs.gt3 ? `${totalGoalsProbs.gt3}%` : '--';
    if (sEq3El) sEq3El.style.display = 'none';  // 隐藏等于3球的显示
    
    // [增强] 更新方法标识
    const methodBadge = document.getElementById('poisson-method-badge');
    const method = prediction?.method || data?.method || 'Poisson';
    if (methodBadge) {
        if (method.includes('Bivariate')) {
            methodBadge.textContent = '🔗 双变量泊松';
            methodBadge.style.background = 'linear-gradient(135deg, rgba(139, 92, 246, 0.2), rgba(168, 85, 247, 0.2))';
        } else if (method.includes('Dixon')) {
            methodBadge.textContent = '🔬 DC修正';
            methodBadge.style.background = 'linear-gradient(135deg, rgba(102, 126, 234, 0.2), rgba(118, 75, 162, 0.2))';
        } else {
            methodBadge.textContent = '📊 标准泊松';
            methodBadge.style.background = 'rgba(102, 126, 234, 0.15)';
        }
    }
    
    // [增强] 显示DC修正信息
    const dcInfoRow = document.getElementById('poisson-dc-info');
    const dcRhoEl = document.getElementById('poisson-dc-rho');
    const dcRho = prediction?.dc_rho || data?.dc_rho || prediction?.rho || data?.rho;
    if (dcInfoRow && dcRhoEl && dcRho !== null && dcRho !== undefined) {
        dcInfoRow.style.display = 'flex';
        dcRhoEl.textContent = dcRho.toFixed(4);
    } else if (dcInfoRow) {
        dcInfoRow.style.display = 'none';
    }
    
    // [增强] 显示时间衰减信息
    const decayInfoRow = document.getElementById('poisson-decay-info');
    const timeDecayApplied = prediction?.time_decay_applied || data?.time_decay_applied;
    if (decayInfoRow) {
        decayInfoRow.style.display = timeDecayApplied ? 'flex' : 'none';
    }
    
    // [增强] 显示市场融合信息
    const fusionInfoRow = document.getElementById('poisson-fusion-info');
    const fusionStatusEl = document.getElementById('poisson-fusion-status');
    if (fusionInfoRow && fusionStatusEl) {
        if (fusion && fusion.applied) {
            fusionInfoRow.style.display = 'flex';
            fusionStatusEl.textContent = '已应用 ✓';
            fusionStatusEl.style.color = '#10b981';
        } else {
            fusionInfoRow.style.display = 'none';
        }
    }

    // 更新比分概率表格（保持传统/融合通用）
    const probabilitiesTbody = document.getElementById('poisson-probabilities-tbody');
    if (probabilitiesTbody) {
        probabilitiesTbody.innerHTML = '';
        const probs = prediction?.probabilities || data?.probabilities;
        if (probs && probs.length > 0) {
            probs.slice(0, 10).forEach(p => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${p?.score ?? '--'}</td>
                    <td>${p?.percentage ?? '--'}%</td>
                    <td>${p?.odds ?? '--'}</td>
                `;
                probabilitiesTbody.appendChild(row);
            });
        } else {
            probabilitiesTbody.innerHTML = '<tr><td colspan="3" class="text-center">--</td></tr>';
        }
    }

    // 在标题附加融合提示与公司数
    try {
        const titleEl = document.getElementById('poisson-modal-title');
        if (titleEl && fusion && typeof fusion.company_count === 'number') {
            const cnt = fusion.company_count;
            const lm = fusion.latest_market_update ? ` · 更新: ${fusion.latest_market_update}` : '';
            titleEl.textContent += `（融合，${cnt}家${lm}）`;
        }
    } catch (e) { /* no-op */ }
}


/**
 * 切换右侧面板的可见性
 * @param {string} panelId 面板ID ('analysis-panel' 或 'settings-panel')
 */
function togglePanel(panelId) {
    const panel = document.getElementById(panelId);
    panel.classList.toggle('d-none');
}

/**
 * 创建泊松分布模态框
 */
function createPoissonModal() {
    if (document.getElementById('poisson-modal')) {
        return;
    }

    const modalHTML = `
        <div class="modal fade" id="poisson-modal" tabindex="-1" role="dialog" aria-labelledby="poissonModalLabel" aria-hidden="true">
            <div class="modal-dialog modal-lg" role="document">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title" id="poisson-modal-title">泊松分布预测</h5>
                        <button type="button" class="close" data-dismiss="modal" aria-label="Close">
                            <span aria-hidden="true">&times;</span>
                        </button>
                    </div>
                    <div class="modal-body">
                        <div class="row">
                            <div class="col-md-6">
                                <h6>预期进球</h6>
                                <p>主队: <strong id="poisson-expected-home-goals"></strong></p>
                                <p>客队: <strong id="poisson-expected-away-goals"></strong></p>
                                <p>总计: <strong id="poisson-expected-total-goals"></strong></p>
                            </div>
                            <div class="col-md-6">
                                <h6>比赛结果概率</h6>
                                <p>主胜: <strong id="poisson-home-win-prob"></strong></p>
                                <p>平局: <strong id="poisson-draw-prob"></strong></p>
                                <p>客胜: <strong id="poisson-away-win-prob"></strong></p>
                            </div>
                        </div>
                        <hr>
                        <h6>最可能比分</h6>
                        <p id="poisson-most-likely-score"></p>
                        <hr>
                        <div class="row">
                            <div class="col-md-6">
                                <h6>大小球概率</h6>
                                <ul id="poisson-over-under-list"></ul>
                            </div>
                            <div class="col-md-6">
                                <h6>比分概率 (Top 10)</h6>
                                <table class="table table-sm">
                                    <thead>
                                        <tr>
                                            <th>比分</th>
                                            <th>概率</th>
                                            <th>赔率</th>
                                        </tr>
                                    </thead>
                                    <tbody id="poisson-probabilities-tbody"></tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;

    document.body.insertAdjacentHTML('beforeend', modalHTML);
}

// 获取开盘区间合理性样式
function getOddsRangeStyle(oddsRange, fundamentalSuggestions, type) {
    // 调试日志
    console.log('getOddsRangeStyle called:', {
        oddsRange,
        fundamentalSuggestions,
        type,
        hasCurrentMatchData: !!window.currentMatchData,
        hasFundamentalAnalysis: !!window.currentMatchData?.fundamentalAnalysis
    });
    
    if (!window.currentMatchData?.fundamentalAnalysis || !oddsRange || oddsRange === '--') {
        console.log('返回空样式 - 原因:', {
            noMatchData: !window.currentMatchData,
            noFundamental: !window.currentMatchData?.fundamentalAnalysis,
            noOddsRange: !oddsRange || oddsRange === '--'
        });
        return { background: '', color: '', title: '' };
    }
    
    const result = checkOddsRangeValidity(oddsRange, fundamentalSuggestions, type);
    
    if (result.valid === '合理') {
        return {
            background: '#e8f5e8',
            color: '#2e7d32',
            title: `合理：${type}开盘在建议范围内`
        };
    } else if (result.valid === '不在建议范围') {
        return {
            background: '#ffeaa7',
            color: '#d63031',
            title: `不合理：${type}开盘不在建议范围内`
        };
    } else {
        return { background: '', color: '', title: result.message || '' };
    }
}

function generateOddsTableRows(company) {
    if (!company) return '<tr><td colspan="10">\u6682\u65e0\u6570\u636e</td></tr>';

    const fundamental = window.currentMatchData?.fundamentalAnalysis;
    const homeConfidenceBand = fundamental?.homeWin?.confidenceLevel || null;
    const drawConfidenceBand = fundamental?.draw?.confidenceLevel || null;
    const awayConfidenceBand = fundamental?.awayWin?.confidenceLevel || null;
    
    // 获取主客队信心分数
    const homeScore = fundamental?.homeWin?.score || null;
    const awayScore = fundamental?.awayWin?.score || null;

    const homeStrengthValue = parseFloat(company.homePowerLevel || 0);
    const awayStrengthValue = parseFloat(company.awayPowerLevel || 0);

    const initialHomeConfidence = company.initial?.homeRange ? lookupConfidenceByText(homeConfidenceBand, company.initial.homeRange) : null;
    const initialAwayConfidence = company.initial?.awayRange ? lookupConfidenceByText(awayConfidenceBand, company.initial.awayRange) : null;
    const currentHomeConfidence = company.current?.homeRange ? lookupConfidenceByText(homeConfidenceBand, company.current.homeRange) : null;
    const currentAwayConfidence = company.current?.awayRange ? lookupConfidenceByText(awayConfidenceBand, company.current.awayRange) : null;

    const initialHomePressureCell = company.initial ? renderBettingPressureCell(homeConfidenceBand, company.initial.homeRange, homeScore, awayScore, awayConfidenceBand) : '--';
    const initialAwayPressureCell = company.initial ? renderBettingPressureCell(awayConfidenceBand, company.initial.awayRange, awayScore, homeScore, homeConfidenceBand) : '--';
    const currentHomePressureCell = company.current ? renderBettingPressureCell(homeConfidenceBand, company.current.homeRange, homeScore, awayScore, awayConfidenceBand) : '--';
    const currentAwayPressureCell = company.current ? renderBettingPressureCell(awayConfidenceBand, company.current.awayRange, awayScore, homeScore, homeConfidenceBand) : '--';

    let html = '';

    if (company.initial) {
        const homeStrengthDisplay = homeStrengthValue > 0 ? homeStrengthValue.toFixed(1) : '--';
        const awayStrengthDisplay = awayStrengthValue > 0 ? awayStrengthValue.toFixed(1) : '--';
        const strengthDiff = homeStrengthValue > 0 && awayStrengthValue > 0 ? (homeStrengthValue - awayStrengthValue).toFixed(1) : '--';

        // 使用规则值的四色标识（不再用合理性背景色）
        const homeRangeClass = getRuleClass(company.initial.homeRuleValue);
        const awayRangeClass = getRuleClass(company.initial.awayRuleValue);

        html += `
            <tr>
                <td><strong>\u521d\u76d8</strong></td>
                <td>${homeStrengthDisplay}</td>
                <td class="${homeRangeClass}" style="cursor: pointer; padding: 4px 8px; font-weight: bold;"
                    onclick="showValidityPopup('${company.initial.homeRange}', window.currentMatchData?.fundamentalAnalysis, '\u4e3b\u961f', event)">
                    ${company.initial.homeRange || '--'}
                </td>
                <td>${initialHomePressureCell}</td>
                <td>${company.initial.drawRange || '--'}</td>
                <td>${awayStrengthDisplay}</td>
                <td class="${awayRangeClass}" style="cursor: pointer; padding: 4px 8px; font-weight: bold;"
                    onclick="showValidityPopup('${company.initial.awayRange}', window.currentMatchData?.fundamentalAnalysis, '\u5ba2\u961f', event)">
                    ${company.initial.awayRange || '--'}
                </td>
                <td>${initialAwayPressureCell}</td>
                <td>${formatNumber(company.initial.ruleDiff)}</td>
                <td class="recommendation-cell">${translateRecommendation(company.initial.recommendedOutcome)}</td>
            </tr>
        `;
    }

    if (company.current) {
        const homeStrengthDisplay = company.homeTierLevel || '--';
        const awayStrengthDisplay = company.awayTierLevel || '--';
        const strengthDiff = homeStrengthValue > 0 && awayStrengthValue > 0 ? (homeStrengthValue - awayStrengthValue).toFixed(1) : '--';

        // 使用规则值的四色标识（不再用合理性背景色）
        const currentHomeRangeClass = getRuleClass(company.current.homeRuleValue);
        const currentAwayRangeClass = getRuleClass(company.current.awayRuleValue);

        html += `
            <tr>
                <td><strong>\u5373\u65f6\u76d8</strong></td>
                <td>${homeStrengthDisplay}</td>
                <td class="${currentHomeRangeClass}" style="cursor: pointer; padding: 4px 8px; font-weight: bold;"
                    onclick="showValidityPopup('${company.current.homeRange}', window.currentMatchData?.fundamentalAnalysis, '\u4e3b\u961f', event)">
                    ${company.current.homeRange || '--'}
                </td>
                <td>${currentHomePressureCell}</td>
                <td>${company.current.drawRange || '--'}</td>
                <td>${awayStrengthDisplay}</td>
                <td class="${currentAwayRangeClass}" style="cursor: pointer; padding: 4px 8px; font-weight: bold;"
                    onclick="showValidityPopup('${company.current.awayRange}', window.currentMatchData?.fundamentalAnalysis, '\u5ba2\u961f', event)">
                    ${company.current.awayRange || '--'}
                </td>
                <td>${currentAwayPressureCell}</td>
                <td>${formatNumber(company.current.ruleDiff)}</td>
                <td class="recommendation-cell">${translateRecommendation(company.current.recommendedOutcome)}</td>
            </tr>
        `;
    }

    return html || '<tr><td colspan="10">\u6682\u65e0\u6570\u636e</td></tr>';
}

function renderDrawSystemCard(ds) {
    const fmt = (v) => v != null ? Number(v).toFixed(2) : '--';
    const fmtTime = (v) => {
        if (!v) return '--';
        const s = String(v);
        return s.length > 16 ? s.substring(5, 16) : s;
    };
    const waterStyle = (wl) => {
        if (!wl) return { bg: '#e2e8f0', color: '#475569' };
        if (wl.includes('高')) return { bg: '#fee2e2', color: '#dc2626' };
        if (wl.includes('低')) return { bg: '#dcfce7', color: '#16a34a' };
        return { bg: '#e0f2fe', color: '#0369a1' };
    };
    const waterRow = (waterLevel, zoneName, standardDraw) => {
        if (!waterLevel) return '';
        const ws = waterStyle(waterLevel);
        return `<div style="display:flex;align-items:center;gap:8px;margin-top:6px;">
            <span style="font-size:0.75rem;font-weight:700;padding:2px 10px;border-radius:12px;background:${ws.bg};color:${ws.color};">${waterLevel}</span>
            ${zoneName ? `<span style="font-size:0.75rem;color:#94a3b8;">${zoneName}</span>` : ''}
            <span style="margin-left:auto;font-size:0.75rem;color:#64748b;">标准平 <strong style="color:#0f766e;">${fmt(standardDraw)}</strong></span>
        </div>`;
    };

    const hasDeviation = ds.deviation != null && ds.deviation !== undefined;
    const hasLongNode = ds.odds_source === 'long_node' && ds.raw_home != null;
    const hasControl = ds.control_home != null;
    const hasCurrent = ds.current_home != null;
    const titleExtra = ds.draw_system_name && ds.draw_system_name !== '长节点控赔'
        ? `<span style="font-size:0.85rem; color:#7c3aed; margin-left:8px; font-weight:500;">(${ds.draw_system_name})</span>` : '';

    let cardHtml = `<div class="detail-card" style="border-left:4px solid #7c3aed;">
        <h3 style="display:flex; align-items:center;">长节点控赔分析${titleExtra}</h3>`;

    if (ds.ou_line != null) {
        cardHtml += `
        <div style="display:flex;align-items:center;background:linear-gradient(90deg,#f1f5fd,#eef2ff);border:1px solid #c7d2fe;border-radius:10px;padding:0.7rem 1.2rem;margin-bottom:1rem;gap:0;">
            <div style="flex:1;text-align:center;">
                <div style="font-size:0.72rem;color:#94a3b8;margin-bottom:2px;">大小球</div>
                <div style="font-size:1.1rem;font-weight:700;color:#1e293b;">${ds.ou_line} 球</div>
            </div>
            <div style="color:#94a3b8;font-size:1.1rem;padding:0 6px;margin-top:10px;">→</div>
            <div style="flex:1;text-align:center;">
                <div style="font-size:0.72rem;color:#94a3b8;margin-bottom:2px;">平系</div>
                <div style="font-size:1.1rem;font-weight:700;color:#7c3aed;">${ds.draw_system_name || '--'}</div>
            </div>
            <div style="color:#94a3b8;font-size:1.1rem;padding:0 6px;margin-top:10px;">→</div>
            <div style="flex:1;text-align:center;">
                <div style="font-size:0.72rem;color:#94a3b8;margin-bottom:2px;">标准平赔</div>
                <div style="font-size:1.2rem;font-weight:800;color:#0f766e;">${fmt(ds.standard_draw)}</div>
            </div>
        </div>`;
    }

    const oddsBlock = (label, dotColor, tagText, tagBg, h, d, a, h94, d94, a94, meta1, waterLevel, zoneName, standardDraw) => `
        <div style="background:rgba(30,41,59,0.03); border-radius:10px; padding:1rem 1.2rem; margin-bottom:1rem; border:1px solid rgba(30,41,59,0.08);">
            <div style="display:flex; align-items:center; margin-bottom:0.8rem;">
                <span style="width:10px;height:10px;border-radius:50%;background:${dotColor};margin-right:8px;flex-shrink:0;"></span>
                <span style="font-weight:700;color:#1e293b;font-size:0.95rem;">${label}</span>
                ${tagText ? `<span style="margin-left:auto;font-size:0.72rem;color:#fff;background:${tagBg};padding:2px 10px;border-radius:4px;">${tagText}</span>` : ''}
            </div>
            <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:0.8rem; margin-bottom:0.6rem;">
                <div style="text-align:center; background:#fff; border-radius:8px; padding:0.6rem 0; border:1px solid rgba(0,0,0,0.06);">
                    <div style="font-size:0.75rem;color:#64748b;">主</div>
                    <div style="font-size:1.3rem;font-weight:700;color:#1e293b;">${h}</div>
                </div>
                <div style="text-align:center; background:#fff; border-radius:8px; padding:0.6rem 0; border:1px solid rgba(124,58,237,0.15);">
                    <div style="font-size:0.75rem;color:#64748b;">平</div>
                    <div style="font-size:1.3rem;font-weight:700;color:#7c3aed;">${d}</div>
                </div>
                <div style="text-align:center; background:#fff; border-radius:8px; padding:0.6rem 0; border:1px solid rgba(0,0,0,0.06);">
                    <div style="font-size:0.75rem;color:#64748b;">客</div>
                    <div style="font-size:1.3rem;font-weight:700;color:#1e293b;">${a}</div>
                </div>
            </div>
            <div style="font-size:0.8rem;color:#475569;">94%体系: ${h94} / ${d94} / ${a94}</div>
            ${waterRow(waterLevel, zoneName, standardDraw)}
            ${meta1 ? `<div style="font-size:0.8rem;color:#475569;margin-top:4px;">${meta1}</div>` : ''}
        </div>`;

    if (hasLongNode) {
        const durText = ds.long_node_duration_hours != null ? `持续 ${Number(ds.long_node_duration_hours).toFixed(1)}h` : '';
        cardHtml += oddsBlock(
            '长节点（定义初赔）', '#7c3aed', '长节点', '#7c3aed',
            fmt(ds.raw_home), fmt(ds.raw_draw), fmt(ds.raw_away),
            fmt(ds.home_94), fmt(ds.draw_94 || ds.actual_draw_94), fmt(ds.away_94),
            `${durText}${durText ? '　' : ''}设定于 ${fmtTime(ds.long_node_time)}`,
            ds.water_level, ds.zone_name, ds.standard_draw
        );
    }

    if (hasControl) {
        cardHtml += oddsBlock(
            '控赔组合', '#f59e0b', '控赔', '#f59e0b',
            fmt(ds.control_home), fmt(ds.control_draw), fmt(ds.control_away),
            fmt(ds.control_home_94), fmt(ds.control_draw_94), fmt(ds.control_away_94),
            `变化于 ${fmtTime(ds.control_time)}`,
            ds.control_water_level, ds.control_zone_name, ds.control_standard_draw
        );
    }

    if (hasCurrent) {
        cardHtml += oddsBlock(
            '即时赔率（终赔）', '#059669', '即时', '#059669',
            fmt(ds.current_home), fmt(ds.current_draw), fmt(ds.current_away),
            fmt(ds.current_home_94), fmt(ds.current_draw_94), fmt(ds.current_away_94),
            ds.current_time ? `更新于 ${fmtTime(ds.current_time)}` : null,
            ds.current_water_level, ds.current_zone_name, ds.current_standard_draw
        );
    }

    if (hasDeviation) {
        const dev = ds.deviation;
        const devText = (dev > 0 ? '+' : '') + dev.toFixed(3);
        let devColor, devBg, devBorder, conclusion;
        if (ds.deviation_direction === '高') {
            devColor = '#dc2626'; devBg = '#fef2f2'; devBorder = '#fecaca';
            conclusion = '实际平赔高于标准值';
        } else if (ds.deviation_direction === '低') {
            devColor = '#15803d'; devBg = '#f0fdf4'; devBorder = '#bbf7d0';
            conclusion = '实际平赔低于标准值';
        } else {
            devColor = '#475569'; devBg = '#f8fafc'; devBorder = '#e2e8f0';
            conclusion = '实际平赔与标准值吻合';
        }
        const favText = ds.favorite_side === 'home' ? '主队' : '客队';

        cardHtml += `
        <div style="background:#fff; border-radius:10px; padding:1rem 1.2rem; border:1px solid #e2e8f0;">
            <div style="display:flex; align-items:center; margin-bottom:1rem;">
                <span style="width:10px;height:10px;border-radius:50%;background:#3b82f6;margin-right:8px;"></span>
                <span style="font-weight:700;color:#1e293b;font-size:0.95rem;">平赔偏差分析</span>
            </div>
            <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:0.8rem; margin-bottom:1rem;">
                <div style="text-align:center; background:#f8fafc; border-radius:8px; padding:0.6rem 0.4rem;">
                    <div style="font-size:0.75rem;color:#64748b;margin-bottom:4px;">一赔方</div>
                    <div style="font-size:1rem;font-weight:700;color:#1e293b;">${favText}</div>
                </div>
                <div style="text-align:center; background:#f8fafc; border-radius:8px; padding:0.6rem 0.4rem;">
                    <div style="font-size:0.75rem;color:#64748b;margin-bottom:4px;">大小球初指</div>
                    <div style="font-size:1rem;font-weight:700;color:#1e293b;">${ds.ou_line || '--'}</div>
                </div>
                <div style="text-align:center; background:#f8fafc; border-radius:8px; padding:0.6rem 0.4rem;">
                    <div style="font-size:0.75rem;color:#64748b;margin-bottom:4px;">平系类型</div>
                    <div style="font-size:1rem;font-weight:700;color:#7c3aed;">${ds.draw_system_name}</div>
                </div>
            </div>
            <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:0.8rem; margin-bottom:1rem;">
                <div style="text-align:center; background:#f8fafc; border-radius:8px; padding:0.6rem 0.4rem;">
                    <div style="font-size:0.75rem;color:#64748b;margin-bottom:4px;">标准平赔</div>
                    <div style="font-size:1rem;font-weight:700;color:#0f766e;">${fmt(ds.standard_draw)}</div>
                </div>
                <div style="text-align:center; background:#f8fafc; border-radius:8px; padding:0.6rem 0.4rem;">
                    <div style="font-size:0.75rem;color:#64748b;margin-bottom:4px;">实际平赔(94%)</div>
                    <div style="font-size:1rem;font-weight:700;color:#1e293b;">${fmt(ds.actual_draw_94)}</div>
                </div>
                <div style="text-align:center; background:#f8fafc; border-radius:8px; padding:0.6rem 0.4rem;">
                    <div style="font-size:0.75rem;color:#64748b;margin-bottom:4px;">偏差</div>
                    <div style="font-size:1.1rem;font-weight:800;color:${devColor};">${devText}</div>
                </div>
            </div>
            <div style="background:${devBg};border:1px solid ${devBorder};border-radius:8px;padding:0.7rem 1rem;text-align:center;font-size:0.9rem;font-weight:700;color:${devColor};">
                ${conclusion}
            </div>
        </div>`;
    }

    cardHtml += '</div>';
    return cardHtml;
}

function generateCompanySummary(match) {
    // 使用从API返回的companySummary数据
    if (!match.companySummary || match.companySummary.total_companies === 0) {
        return '<div class="company-summary"><div class="loading">暂无统计数据</div></div>';
    }
    
    const summary = match.companySummary;
    
    return `
        <div class="company-summary">
            <h4 style="color: #c62828; margin-bottom: 1rem; font-size: 1.1rem;">推荐公司总结 (${formatNumber(summary.total_companies, 0)}家公司)</h4>
            
            <!-- 初盘统计 -->
            <div style="margin-bottom: 1.5rem;">
                <h5 style="color: #666; margin-bottom: 0.5rem;">初盘态度分布</h5>
                <div class="summary-stats">
                    <div class="stat-card home-stat">
                        <div class="stat-title">主胜推荐</div>
                        <div class="stat-number">${formatNumber(summary.initial?.home?.count, 0)}家</div>
                        <div class="stat-percent">${formatNumber(summary.initial?.home?.percentage, 0)}%</div>
                    </div>
                    <div class="stat-card draw-stat">
                        <div class="stat-title">平局推荐</div>
                        <div class="stat-number">${formatNumber(summary.initial?.draw?.count, 0)}家</div>
                        <div class="stat-percent">${formatNumber(summary.initial?.draw?.percentage, 0)}%</div>
                    </div>
                    <div class="stat-card away-stat">
                        <div class="stat-title">客胜推荐</div>
                        <div class="stat-number">${formatNumber(summary.initial?.away?.count, 0)}家</div>
                        <div class="stat-percent">${formatNumber(summary.initial?.away?.percentage, 0)}%</div>
                    </div>
                </div>
            </div>
            
            <!-- 即时盘统计 -->
            <div>
                <h5 style="color: #666; margin-bottom: 0.5rem;">即时盘态度分布</h5>
                <div class="summary-stats">
                    <div class="stat-card home-stat">
                        <div class="stat-title">主胜推荐</div>
                        <div class="stat-number">${formatNumber(summary.current?.home?.count, 0)}家</div>
                        <div class="stat-percent">${formatNumber(summary.current?.home?.percentage, 0)}%</div>
                    </div>
                    <div class="stat-card draw-stat">
                        <div class="stat-title">平局推荐</div>
                        <div class="stat-number">${formatNumber(summary.current?.draw?.count, 0)}家</div>
                        <div class="stat-percent">${formatNumber(summary.current?.draw?.percentage, 0)}%</div>
                    </div>
                    <div class="stat-card away-stat">
                        <div class="stat-title">客胜推荐</div>
                        <div class="stat-number">${formatNumber(summary.current?.away?.count, 0)}家</div>
                        <div class="stat-percent">${formatNumber(summary.current?.away?.percentage, 0)}%</div>
                    </div>
                </div>
            </div>

        </div>
    `;
}

// 推荐结果映射规则
const RECOMMENDATION_MAPPING = {
    '主让1胜': 'home',
    '主让1平': 'home',
    '主让1负': 'draw',  // 简化处理
    '主让2胜': 'home',
    '主让2平': 'home',
    '客让1胜': 'away',
    '客让1平': 'away',
    '客让2胜': 'away',
    '客让2平': 'away',
    '主受1胜': 'home',  // 简化处理
    '客受1胜': 'away',  // 简化处理
    '平': 'draw',
    '双平': 'draw',  // 简化处理
    '双平偏平': 'draw',
    '双平偏让平': 'draw'
};

function calculateRecommendationSummary(companies) {
    const summary = {
        home: { count: 0, companies: [] },
        draw: { count: 0, companies: [] },
        away: { count: 0, companies: [] },
        total: companies.length
    };
    
    companies.forEach(company => {
        const companyName = COMPANY_MAPPING[company.companyId] || company.companyName || '未知公司';
        const recommendation = company.recommendedOutcome || 
                             (company.current && company.current.recommendedOutcome) ||
                             (company.initial && company.initial.recommendedOutcome);
        
        if (recommendation) {
            let result = null;
            
            // 首先尝试使用映射表
            if (RECOMMENDATION_MAPPING[recommendation]) {
                result = RECOMMENDATION_MAPPING[recommendation];
            }
            // 如果映射表没有，使用原有逻辑作为后备
            else if (recommendation === 'home' || recommendation === '3') {
                result = 'home';
            } else if (recommendation === 'draw' || recommendation === '1') {
                result = 'draw';
            } else if (recommendation === 'away' || recommendation === '0') {
                result = 'away';
            }
            // 最后使用简单的字符串匹配作为最后手段
            else if (recommendation.includes('主')) {
                result = 'home';
            } else if (recommendation.includes('客')) {
                result = 'away';
            } else if (recommendation.includes('平')) {
                result = 'draw';
            }
            
            // 根据结果更新统计
            if (result === 'home') {
                summary.home.count++;
                summary.home.companies.push(companyName);
            } else if (result === 'draw') {
                summary.draw.count++;
                summary.draw.companies.push(companyName);
            } else if (result === 'away') {
                summary.away.count++;
                summary.away.companies.push(companyName);
            }
        }
    });
    
    // 计算百分比
    summary.home.percentage = (summary.home.count / summary.total * 100).toFixed(1);
    summary.draw.percentage = (summary.draw.count / summary.total * 100).toFixed(1);
    summary.away.percentage = (summary.away.count / summary.total * 100).toFixed(1);
    
    return summary;
}

// 生成赔率卡片
function generateOddsCard(match) {
    // 获取主要公司的赔率数据（优先显示香港马会、立博等主流公司）
    if (!match.companyAnalyses || match.companyAnalyses.length === 0) {
        return `
            <div class="odds-card">
                <div class="odds-card-header">实时赔率</div>
                <div style="text-align: center; color: #cccccc; padding: 1rem;">
                    暂无赔率数据
                </div>
            </div>
        `;
    }
    
    // 查找优先公司（香港马会432、立博115、威廉希尔80等）
    const priorityCompanies = [ 115, 432,80, 791, 517, 4, 976];
    let mainCompany = null;
    
    for (let companyId of priorityCompanies) {
        mainCompany = match.companyAnalyses.find(c => c.companyId == companyId);
        if (mainCompany) break;
    }
    
    // 如果没找到优先公司，使用第一个公司
    if (!mainCompany) {
        mainCompany = match.companyAnalyses[0];
    }
    
    const companyName = COMPANY_MAPPING[mainCompany.companyId] || mainCompany.companyName || '未知公司';
    
    // 获取初盘和即时盘数据
    const initialOdds = mainCompany.initial || {};
    const currentOdds = mainCompany.current || {};
    
    // 生成赔率变化信息
    function getOddsChange(initial, current) {
        if (!initial || !current || !initial.odds || !current.odds) {
            return { change: 'same', arrow: '—', text: '无变化' };
        }
        
        const initialValue = parseFloat(initial.odds.home || initial.odds.draw || initial.odds.away || 0);
        const currentValue = parseFloat(current.odds.home || current.odds.draw || current.odds.away || 0);
        
        if (initialValue === 0 || currentValue === 0) {
            return { change: 'same', arrow: '—', text: '无变化' };
        }
        
        if (currentValue < initialValue) {
            return { change: 'down', arrow: '↓', text: '下降' };
        } else if (currentValue > initialValue) {
            return { change: 'up', arrow: '↑', text: '上升' };
        } else {
            return { change: 'same', arrow: '—', text: '无变化' };
        }
    }
    
    const homeChange = getOddsChange(
        { odds: { home: initialOdds.odds?.home } }, 
        { odds: { home: currentOdds.odds?.home } }
    );
    const drawChange = getOddsChange(
        { odds: { draw: initialOdds.odds?.draw } }, 
        { odds: { draw: currentOdds.odds?.draw } }
    );
    const awayChange = getOddsChange(
        { odds: { away: initialOdds.odds?.away } }, 
        { odds: { away: currentOdds.odds?.away } }
    );
    
    return `
        <div class="odds-card">
            <div class="odds-card-header">实时赔率对比</div>
            <div class="odds-grid">
                <div class="odds-item home-odds">
                    <div class="odds-label">🏠 主胜</div>
                    <div class="odds-value">${formatNumber(currentOdds.odds?.home) || formatNumber(initialOdds.odds?.home)}</div>
                    <div class="odds-change ${homeChange.change}">
                        <span class="odds-change-arrow">${homeChange.arrow}</span>
                        <span>${homeChange.text}</span>
                    </div>
                </div>
                <div class="odds-item draw-odds">
                    <div class="odds-label">⚖️ 平局</div>
                    <div class="odds-value">${formatNumber(currentOdds.odds?.draw) || formatNumber(initialOdds.odds?.draw)}</div>
                    <div class="odds-change ${drawChange.change}">
                        <span class="odds-change-arrow">${drawChange.arrow}</span>
                        <span>${drawChange.text}</span>
                    </div>
                </div>
                <div class="odds-item away-odds">
                    <div class="odds-label">✈️ 客胜</div>
                    <div class="odds-value">${formatNumber(currentOdds.odds?.away) || formatNumber(initialOdds.odds?.away)}</div>
                    <div class="odds-change ${awayChange.change}">
                        <span class="odds-change-arrow">${awayChange.arrow}</span>
                        <span>${awayChange.text}</span>
                    </div>
                </div>
            </div>
            <div class="odds-company-info">
                数据来源：${companyName}
                ${initialOdds.odds && currentOdds.odds ? 
                    ` | 初盘: ${formatNumber(initialOdds.odds.home)} ${formatNumber(initialOdds.odds.draw)} ${formatNumber(initialOdds.odds.away)}` : ''
                }
            </div>
        </div>
    `;
}

// [性能优化] 渲染"加载更多公司"按钮
function renderLoadMoreButton() {
    const container = document.getElementById('loadMoreContainer');
    if (!container) {
        console.log('loadMoreContainer 元素不存在');
        return;
    }

    const remainingCount = window.totalCompanyCount - window.allCompanyAnalyses.length;
    console.log(`加载更多按钮: 剩余 ${remainingCount} 家公司 (总数: ${window.totalCompanyCount}, 已加载: ${window.allCompanyAnalyses.length})`);

    if (remainingCount > 0) {
        container.innerHTML = `
            <button onclick="loadAllCompanies()" class="back-btn" style="margin-bottom: 0;">
                加载剩余 ${remainingCount} 家公司数据...
            </button>
        `;
    } else {
        container.innerHTML = '';
    }
}

// [性能优化] 加载所有公司的赔率数据
async function loadAllCompanies() {
    const loadButton = document.querySelector('#loadMoreContainer button');
    try {
        loadButton.textContent = '加载中...';
        loadButton.disabled = true;

        // 直接使用已保存的完整公司列表，无需再次请求API
        window.allCompanyAnalyses = window.fullCompanyAnalyses;
        
        const select = document.getElementById('companySelect');
        const currentSelection = select.value;

        // 重新渲染下拉框，显示所有公司
        select.innerHTML = window.allCompanyAnalyses.map(company => 
            `<option value="${company.companyId}">${company.companyName || '未知公司'}</option>`
        ).join('');

        // 尝试保持之前的选择，如果不存在则选择第一个
        if (window.allCompanyAnalyses.find(c => c.companyId == currentSelection)) {
            select.value = currentSelection;
        }
        
        // 隐藏加载按钮
        document.getElementById('loadMoreContainer').innerHTML = '';
        
        // 成功加载提示
        console.log(`已加载全部 ${window.allCompanyAnalyses.length} 家公司的赔率分析`);

    } catch (error) {
        console.error('加载失败:', error);
        loadButton.textContent = '加载失败，请重试';
        loadButton.disabled = false;
    }
}


function updateOddsTable() {
    const select = document.getElementById('companySelect');
    const selectedCompanyId = select.value;
    const company = window.allCompanyAnalyses.find(c => c.companyId == selectedCompanyId);
    
    if (company) {
        document.getElementById('oddsTableBody').innerHTML = generateOddsTableRows(company);
    }
}

// 应用开盘区间颜色的函数
function applyOddsRangeColors() {
    // 确保必要的数据存在
    if (!window.currentMatchData || !window.currentMatchData.fundamentalAnalysis) {
        return;
    }
    
    const fundamentalAnalysis = window.currentMatchData.fundamentalAnalysis;
    const companySelect = document.getElementById('companySelect');
    const currentIndex = companySelect ? parseInt(companySelect.value) : 0;
    const currentCompany = window.allCompanyAnalyses?.[currentIndex];
    
    if (!currentCompany) return;
    
    // 辅助函数：判断区间是否合理
    function isRangeValid(oddsRange, suggestions) {
        if (!oddsRange || oddsRange === '--' || !suggestions) return null;
        
        let suggestionsList = [];
        try {
            if (typeof suggestions === 'string') {
                suggestionsList = JSON.parse(suggestions);
            } else if (Array.isArray(suggestions)) {
                suggestionsList = suggestions;
            }
        } catch (e) {
            return null;
        }
        
        const rangeParts = oddsRange.split('-');
        if (rangeParts.length !== 2) return null;
        
        const rangeMin = parseFloat(rangeParts[0]);
        const rangeMax = parseFloat(rangeParts[1]);
        
        if (isNaN(rangeMin) || isNaN(rangeMax)) return null;
        
        for (const suggestion of suggestionsList) {
            const sugParts = suggestion.split('-');
            if (sugParts.length !== 2) continue;
            
            const sugMin = parseFloat(sugParts[0]);
            const sugMax = parseFloat(sugParts[1]);
            
            if (isNaN(sugMin) || isNaN(sugMax)) continue;
            
            if (rangeMin <= sugMax && rangeMax >= sugMin) {
                return true;
            }
        }
        
        return false;
    }
    
    // 应用颜色到表格行
    const tableRows = document.querySelectorAll('#oddsTableBody tr');
    
    tableRows.forEach((row, index) => {
        const cells = row.querySelectorAll('td');
        if (cells.length < 7) return;
        
        const isInitial = index === 0;
        const data = isInitial ? currentCompany.initial : currentCompany.current;
        
        if (!data) return;
        
        // 主队区间 (第3列)
        const homeRangeCell = cells[2];
        if (homeRangeCell && data.homeRange && data.homeRange !== '--') {
            const isValid = isRangeValid(data.homeRange, fundamentalAnalysis.homeWin?.oddsSuggestions);
            
            if (isValid === true) {
                homeRangeCell.style.background = '#e8f5e8';
                homeRangeCell.style.color = '#2e7d32';
            } else if (isValid === false) {
                homeRangeCell.style.background = '#ffeaa7';
                homeRangeCell.style.color = '#d63031';
            }
        }
        
        // 客队区间 (第7列)
        const awayRangeCell = cells[6];
        if (awayRangeCell && data.awayRange && data.awayRange !== '--') {
            const isValid = isRangeValid(data.awayRange, fundamentalAnalysis.awayWin?.oddsSuggestions);
            
            if (isValid === true) {
                awayRangeCell.style.background = '#e8f5e8';
                awayRangeCell.style.color = '#2e7d32';
            } else if (isValid === false) {
                awayRangeCell.style.background = '#ffeaa7';
                awayRangeCell.style.color = '#d63031';
            }
        }
    });
}

// 视图切换
function showList() {
    document.getElementById('detailPage').classList.remove('active');
    document.getElementById('listPage').style.display = 'block';
    currentMatchId = null;
    startAutoRefresh(300);
}

function showDetail(matchId) {
    document.getElementById('listPage').style.display = 'none';
    document.getElementById('detailPage').classList.add('active');
    currentMatchId = matchId;
    
    fetchMatchDetail(matchId);
    
    // 根据比赛状态设置刷新频率
    const match = allMatches.find(m => m.matchId === matchId);
    if (match) {
        if (match.matchStatus === 'scheduled') {
            startAutoRefresh(300);
        } else if (match.matchStatus === 'live') {
            startAutoRefresh(300);
        } else {
            stopAutoRefresh();
        }
    }
}

// 辅助函数
function showDetailLoading() {
    document.getElementById('detailContent').innerHTML = `
        <div class="loading">
            <div class="spinner"></div>
            <p>加载详情中...</p>
        </div>
    `;
}

function showError(message) {
    alert(message);
}

function updateFilters() {
    const leagues = [...new Map(allMatches.map(m => [m.leagueId, m.leagueName])).entries()];
    const leagueFilter = document.getElementById('leagueFilter');
    
    leagueFilter.innerHTML = '<option value="">全部联赛</option>' + 
        leagues.map(([id, name]) => `<option value="${id}">${name || '未知联赛'}</option>`).join('');
}

function updateLastUpdateTime() {
    const now = new Date();
    const timeStr = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`;
    document.getElementById('last-update').textContent = `更新时间: ${timeStr}`;
}

// 自动刷新
function startAutoRefresh(seconds) {
    stopAutoRefresh();
    
    refreshInterval = setInterval(() => {
        if (currentMatchId) {
            fetchMatchDetail(currentMatchId);
        } else {
            fetchMatches();
        }
    }, seconds * 1000);
}

function stopAutoRefresh() {
    if (refreshInterval) {
        clearInterval(refreshInterval);
        refreshInterval = null;
    }
}

// 事件监听
document.addEventListener('DOMContentLoaded', () => {
    // 筛选器事件
    document.getElementById('leagueFilter').addEventListener('change', renderMatchesList);
    document.getElementById('dateFilter').addEventListener('change', renderMatchesList);
    document.getElementById('customDate').addEventListener('change', renderMatchesList);
    
    // 状态筛选器特殊处理：选择"已结束"时重新请求数据
    document.getElementById('statusFilter').addEventListener('change', function() {
        const selectedStatus = this.value;
        if (selectedStatus === 'finished') {
            // 查询已完成比赛，需要重新请求更大范围的数据
            fetchMatches('finished');
        } else if (selectedStatus === '') {
            // 全部状态，重新请求默认数据
            fetchMatches();
        } else {
            // 其他状态（scheduled, live），只需前端过滤
            renderMatchesList();
        }
    });
    
    // [新增] 泊松模态框关闭事件
    const closeModal = () => {
        document.getElementById('poisson-modal').style.display = 'none';
        document.getElementById('poisson-modal-backdrop').style.display = 'none';
    };
    document.getElementById('poisson-modal-close').addEventListener('click', closeModal);
    document.getElementById('poisson-modal-backdrop').addEventListener('click', closeModal);

    // 初始化
    fetchMatches();
    startAutoRefresh(300);
    
    // 页面可见性变化处理
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            stopAutoRefresh();
        } else {
            if (currentMatchId) {
                fetchMatchDetail(currentMatchId);
            } else {
                fetchMatches();
            }
            startAutoRefresh(300);
        }
    });
});

// 开盘区间合理性判断函数
function checkOddsRangeValidity(oddsRange, fundamentalSuggestions, type) {
    // 调试日志
    console.log('checkOddsRangeValidity called:', {
        oddsRange,
        fundamentalSuggestions,
        type
    });
    
    // 检查数据完整性
    if (!oddsRange || oddsRange === '--' || !fundamentalSuggestions) {
        console.log('数据不完整 - 返回默认值');
        return { 
            valid: '数据不完整', 
            message: '数据不完整，无法判断',
            color: '#999'
        };
    }
    
    // 解析基本面建议（JSON字符串转数组）
    let suggestionsList = [];
    try {
        if (typeof fundamentalSuggestions === 'string') {
            // 如果是JSON字符串，解析它
            suggestionsList = JSON.parse(fundamentalSuggestions);
        } else if (Array.isArray(fundamentalSuggestions)) {
            // 如果已经是数组
            suggestionsList = fundamentalSuggestions;
        }
    } catch (e) {
        console.error('解析建议列表失败:', e);
        return { 
            valid: '数据格式错误', 
            message: '建议数据格式错误',
            color: '#999'
        };
    }
    
    // 标准化盘口描述（去除可能的编号前缀）
    const normalizeDescription = (desc) => {
        // 去除类似 "1." "2." 这样的编号
        return desc.replace(/^\d+\.\s*/, '').trim();
    };
    
    const normalizedOddsRange = normalizeDescription(oddsRange);
    const normalizedSuggestions = suggestionsList.map(s => normalizeDescription(s));
    
    // 判断赔率盘口是否在建议列表中
    const isInList = normalizedSuggestions.some(suggestion => 
        suggestion === normalizedOddsRange || 
        suggestion.includes(normalizedOddsRange) || 
        normalizedOddsRange.includes(suggestion)
    );
    
    if (isInList) {
        return {
            valid: '合理',
            message: `${type}开盘 "${oddsRange}" 在建议范围内`,
            color: '#4CAF50'
        };
    } else {
        return {
            valid: '不在建议范围',
            message: `${type}开盘 "${oddsRange}" 不在建议列表中<br>建议: ${normalizedSuggestions.join(', ')}`,
            color: '#FF9800'
        };
    }
}

// 显示合理性判断弹框
function showValidityPopup(oddsRange, fundamentalData, type, event) {
    // 阻止事件冒泡
    if (event) {
        event.stopPropagation();
    }
    
    // 调试：打印传入的数据
    console.log('调试信息：');
    console.log('oddsRange:', oddsRange);
    console.log('fundamentalData:', fundamentalData);
    console.log('type:', type);
    
    let fundamentalSuggestion;
    if (type === '主队') {
        fundamentalSuggestion = fundamentalData?.homeWin?.oddsSuggestions;
    } else if (type === '客队') {
        fundamentalSuggestion = fundamentalData?.awayWin?.oddsSuggestions;
    } else if (type === '平局') {
        fundamentalSuggestion = fundamentalData?.draw?.oddsSuggestions;
    }
    
    console.log('fundamentalSuggestion:', fundamentalSuggestion);
    
    const result = checkOddsRangeValidity(oddsRange, fundamentalSuggestion, type);
    
    // 创建弹框
    const popup = document.createElement('div');
    popup.className = 'validity-popup';
    popup.style.cssText = `
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        background: white;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        z-index: 10000;
        min-width: 300px;
        max-width: 500px;
    `;
    
    popup.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
            <h3 style="margin: 0; color: ${result.color};">${result.valid}</h3>
            <div style="display: flex; align-items: center; gap: 10px;">
                <span id="countdown" style="font-size: 12px; color: #999;">5秒后关闭</span>
                <button onclick="clearTimeout(window.popupTimer); this.parentElement.parentElement.parentElement.remove(); document.getElementById('popup-backdrop').remove();" 
                        style="background: none; border: none; font-size: 24px; cursor: pointer; color: #999;">×</button>
            </div>
        </div>
        <div style="color: #333; line-height: 1.6;">
            ${result.message}
        </div>
    `;
    
    // 创建背景遮罩
    const backdrop = document.createElement('div');
    backdrop.id = 'popup-backdrop';
    backdrop.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.5);
        z-index: 9999;
    `;
    backdrop.onclick = function() {
        clearTimeout(window.popupTimer);
        popup.remove();
        backdrop.remove();
    };
    
    document.body.appendChild(backdrop);
    document.body.appendChild(popup);
    
    // 倒计时自动关闭
    let countdown = 5;
    const countdownElement = document.getElementById('countdown');
    
    const updateCountdown = () => {
        countdown--;
        if (countdown > 0) {
            countdownElement.textContent = `${countdown}秒后关闭`;
            window.popupTimer = setTimeout(updateCountdown, 1000);
        } else {
            popup.remove();
            backdrop.remove();
        }
    };
    
    window.popupTimer = setTimeout(updateCountdown, 1000);
}

// 切换主队合理区间显示
function toggleHomeRange(event) {
    event.stopPropagation();
    const detail = document.getElementById('home-range-detail');
    const btn = event.target;
    if (detail.style.display === 'none') {
        detail.style.display = 'block';
        btn.textContent = '隐藏区间 ▲';
    } else {
        detail.style.display = 'none';
        btn.textContent = '显示区间 ▼';
    }
}

// 切换客队合理区间显示
function toggleAwayRange(event) {
    event.stopPropagation();
    const detail = document.getElementById('away-range-detail');
    const btn = event.target;
    if (detail.style.display === 'none') {
        detail.style.display = 'block';
        btn.textContent = '隐藏区间 ▲';
    } else {
        detail.style.display = 'none';
        btn.textContent = '显示区间 ▼';
    }
}

// 全局函数暴露
window.showList = showList;
window.showDetail = showDetail;
window.updateOddsTable = updateOddsTable;
window.showValidityPopup = showValidityPopup;
window.getOddsRangeStyle = getOddsRangeStyle;
window.checkOddsRangeValidity = checkOddsRangeValidity;
window.applyOddsRangeColors = applyOddsRangeColors;
window.toggleHomeRange = toggleHomeRange;
window.toggleAwayRange = toggleAwayRange;
window.currentMatchData = null; // 存储当前比赛数据
