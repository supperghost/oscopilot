# -*- coding: utf-8 -*-

import subprocess
import json
import urllib.parse
import requests
import time
import datetime
from datetime import datetime,timedelta
from dataclasses import dataclass

url = "https://grafana.byted.org/api/datasources/proxy/39171/query?db=iaas_metrics&epoch=ms"

headers = {
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Origin": "https://grafana.byted.org",
    "Pragma": "no-cache",
    "Referer": "https://grafana.byted.org",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
    "accept": "application/json, text/plain, */*",
    "content-type": "application/x-www-form-urlencoded",
    "sec-ch-ua": '"Google Chrome";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "x-grafana-org-id": "1"
}

cookies = {
   
}

data_disk = {
    "q": 'SELECT max("value") FROM "Inner_DiskUsageUtilization" WHERE ("ResourceId" =~ /^(i-yeazlrqio0ajrd8213e7|i-yeazlrqio0ajrd821tz7|i-yeazlrqio0ajrd8242ff|i-yeazlrqio0ajrd824i36|i-yeazlu5lvk8lu7j7250l|i-yeazlu5lvk8lu7j73yf3|i-yeazlu5lvk8lu7j75t5o|i-yeazlu5lvk8lu7j76qj2|i-yeaznog4qonr7giml6c9|i-yeaznog4qonr7gimmq8b|i-yeaznog4qonr7gimnqu2|i-yeaznog4qonr7gimpr42|i-yeb41fdxxc8lu7jxop5l|i-yeb41fdxxc8lu7jxwwe6|i-yebclrmkg0nr7giitkve|i-yebu9ughs0nr7gji4qx0|i-yebuaa7z7knr7gij1ri3|i-yebuaa7z7knr7gij2mq5|i-yebuaa7z7knr7gij4hho|i-yebuaa7z7knr7gij5vt6|i-yebuaa7z7knr7gij7bef|i-yebubhgcg0ajrd7v7z0c|i-yebubhgcg0ajrd7v99sw|i-yebubhgcg0ajrd7vatzw|i-yebubhgcg0ajrd7vcmfy|i-yebubhgcg0ajrd7ven9i|i-yebubhgcg0ajrd7vfk8s|i-yebubhgcg0ajrd7vh1nw|i-yebubhgcg0ajrd7vhmeg|i-yebubhgcg0ajrd7vjbqv|i-yebubhgcg0ajrd7vlely|i-yebubhgcg0ajrd7vmw2m|i-yebubhgcg0ajrd7vnx2o|i-yebubhgcg0ajrd7voqv7|i-yebubhgcg0ajrd7vrabj|i-yebubhgcg0ajrd7vryya|i-yebubhgcg0ajrd7vtspz|i-yebubhgcg0ajrd7vve3k|i-yebubhgcg0ajrd7vwy0s|i-yebubhgcg0ajrd7vxbcq|i-yebubhgcg0ajrd7vz0az|i-yebubhgcg0ajrd7w0o3o|i-yebubhgcg0ajrd7w1a31|i-yebubhgcg0ajrd7w2xdd|i-yebubhgcg0ajrd7w50xv|i-yebubhgcg0ajrd7w6cwn|i-yebukfmnls8lu7jbk0hd|i-yebuuaqi2osoborzmamf|i-yebuuaqi2osoborzo4oq|i-yebuuaqi2osoborzozml|i-yebuuaqi2osoborzr4l9|i-yebuuaqi2osoborzsf7a|i-yebuuaqi2osoborztud3|i-yebuuaqi2osoborzu6pv|i-yebuuaqi2osoborzwav9|i-yebuuaqi2osoborzxv98|i-yebuuaqi2osoborzyjpz|i-yebuuaqi2osobos00hm3|i-yebuuaqi2osobos01yyn|i-yebuuaqi2osobos03iw2|i-yebuuaqi2osobos04ypn|i-yebuuaqi2osobos05do0|i-yebuuaqi2osobos07iyh|i-yebuuaqi2osobos090u5|i-yebuuaqi2osobos0a1ws|i-yebuuaqi2osobos0b6gd|i-yebuuaqi2osobos0cmbz|i-yebuuaqi2osobos0dydb|i-yebuuaqi2osobos0fwa1|i-yebuuaqi2osobos0hqje|i-yebuuaqi2osobos0i0yl|i-yebuuaqi2osobos0kdbk|i-yebuuaqi2osobos0li5g|i-yebuuaqi2osobos0nbur|i-yebuuaqi2osobos0oc35|i-yebuuaqi2osobos0pk4w|i-yebw7hpdz4nr7ginomyh|i-yebw7hpdz4nr7ginqj5y|i-yebw7hpdz4nr7ginr3xx|i-yebw7hpdz4nr7ginto00|i-yebw7hpdz4nr7ginupp4|i-yebw7hpdz4nr7ginw78p|i-yebw7hpdz4nr7ginxcz1|i-yebw7hpdz4nr7ginygrf|i-yebw7hpdz4nr7gio06d5|i-yebw7hpdz4nr7gio1jak|i-yebw7rf5dsnr7giqsff6|i-yebw7rf5dsnr7giqtjcp|i-yebw7rf5dsnr7giqun8a|i-yebw7rf5dsnr7giqwalz|i-yebw7rf5dsnr7giqx8nc|i-yebw7rf5dsnr7giqzf5l|i-yebw7rf5dsnr7gir10w7|i-yebw7rf5dsnr7gir1n3t|i-yebw7rf5dsnr7gir3ngx|i-yebw7rf5dsnr7gir4e42|i-yebw7rf5dsnr7gir5b5c|i-yebw7rf5dsnr7gir7l09|i-yebw7rf5dsnr7gir846h|i-yebw7rf5dsnr7giraqzk|i-yebw7rf5dsnr7giraynb|i-yebw7rf5dsnr7gircjsu|i-yebw7rf5dsnr7giredd8|i-yebw7rf5dsnr7girgcyt|i-yebw7rf5dsnr7girhla0|i-yebw7rf5dsnr7girj57i|i-yebw921q0w8lu7j1arbg|i-yebwbd5nnksobos4e08v|i-yebwbgighs3z47gk16p3|i-yebww2rdog3z47gfd2zc|i-yebww340sg3z47gfkbfp|i-yebwwavjswsoborxzfis|i-yebwwavjswsobory0v8y|i-yebwwavjswsobory28b5|i-yebwwavjswsobory3b6l|i-yebwwavjswsobory4pzj|i-yebwwavjswsobory6beo|i-yebwwavjswsobory7kv9|i-yebwwavjswsobory9364|i-yebwwavjswsoboryamrq|i-yebwwavjswsoborycav5|i-yebwwavjswsoborydptq|i-yebwwavjswsoboryeezk|i-yebwwavjswsoboryglbx|i-yebwwavjswsoboryhtgh|i-yebwwavjswsoboryinvb|i-yebwwavjswsoborykv4z|i-yebwwavjswsoborym28h|i-yebwwavjswsoborymxst|i-yebwwavjswsoboryolyg|i-yebwwbruv48lu7iynztn|i-yebwwbruv48lu7iyp663|i-yebwwbruv48lu7iyqru2|i-yebwwbruv48lu7iys9uw|i-yebwwbruv48lu7iytitw|i-yebwwbruv48lu7iyu7kk|i-yebwwbruv48lu7iyvltb|i-yebwwbruv48lu7iyxcuf|i-yebwwbruv48lu7iyxyuu|i-yebwwbruv48lu7iyzwle|i-yebwwbruv48lu7iz23zl|i-yebwwbruv48lu7iz2su5|i-yebwwbruv48lu7iz4hd4|i-yebwwbruv48lu7iz5uky|i-yebwwbruv48lu7iz715q|i-yebwwbruv48lu7iz8eoi|i-yebwwbruv48lu7iz9eez|i-yebwwbruv48lu7izaud2|i-yebwwbruv48lu7izcd88|i-yebx119pts3z47gwvmzk|i-yebx13negwnr7gicb0vt|i-yebx1895hc8lu7j3xbbx|i-yebx1895hc8lu7j3yiu0|i-yebx1895hc8lu7j3zhr9|i-yebx1cjny83z47genyu4|i-yebx5peewwajrd7e68zd|i-yebx5peewwajrd7e85wj|i-yebx5peewwajrd7e92jv|i-yebx5peewwajrd7ebeyk|i-yec1eri8sgnr7gicr5hg|i-yec1eri8sgnr7gicsddr|i-yec1eri8sgnr7gicuvoh|i-yec1esbqpsnr7gifis3i|i-yec1esbqpsnr7gifk9fm|i-yec1esbqpsnr7giflq85|i-yec4saes5c2kyw5vcmvs|i-yec4saes5c2kyw5veds0|i-yec4scd0jk3z47h1rx3a|i-yec4scd0jk3z47h1tfxx|i-yec4svehog2kyw5pvqcj|i-yec4svehog2kyw5py6oq|i-yec4svehog2kyw5pywc2|i-yec4svehog2kyw5q19qd|i-yec4svehog2kyw5q2eeu|i-yec4svehog2kyw5q2wd1|i-yec4tdmgw02kyw5jnnqk|i-yec4tdmgw02kyw5kmesm|i-yec4xkl43ksobosdksh0|i-yec4xkl43ksobosdnaic|i-yec4y8w7wgsobosdpcoz|i-yec4yaou0wnr7giafd33|i-yec4ycbtvk2kyw5coh7n|i-yec4ydt7ggnr7gii7f5r|i-yec4yindvksobosk7gge|i-yec4yindvksobosk94uz|i-yec56exrls3z47ggb9on|i-yec56exrls3z47ggbu68|i-yec56f905c8lu7j9jnas|i-yec56f905c8lu7j9karj|i-yec56fn1tssobos3eq5s|i-yec56fn1tssobos3fe61|i-yec56g13i88lu7jayh0c|i-yec56g13i88lu7jaykbe|i-yec56i7rb4soboryzoyi|i-yec56i7rb4soborz0wz5|i-yec56iq0ow3z47gztlhz|i-yec56iq0ow3z47gzuana|i-yec5d0wt8g3z47gmpe4j|i-yec5d0wt8g3z47gmqi87|i-yec5d0wt8g3z47gmruu4|i-yec5d0wt8g3z47gmtph8|i-yec5d1auww2kyw5l257d|i-yec5d1auww2kyw5l3psd|i-yec5d1auww2kyw5l4zwt|i-yec5d1auww2kyw5l6ld7|i-yec5d1owlcnr7gilgof7|i-yec5d1owlcnr7gilipj8|i-yec5d1owlcnr7giljrjo|i-yec5d1owlcnr7gill2dn|i-yec5d22y9snr7gimsnnl|i-yec5d22y9snr7gimubvw|i-yec5d22y9snr7gimvh4s|i-yec5d22y9snr7gimwlx9|i-yec75lwirknr7ginu0n5|i-yec75lwirknr7ginw069|i-yec75lwirknr7ginwupx|i-yec75n2nswnr7gin5rje|i-yec75n2nswnr7gin767l|i-yec75n2nswnr7gin8owc|i-yec9o2cd8gsoborx8lzb|i-yec9o2p0cgsobosc93i3|i-yec9o34glcajrd7k0n6u|i-yec9o3ii9ssoboryo1px|i-yecc94i7swsoboscda8i|i-yecc94i7swsoboscez5p|i-yecc94i7swsoboscgk5n|i-yecc98iwao3z47ghv229|i-yecc98iwao3z47ghvx9u|i-yeccrj5mgwnr7giocw47|i-yeccrj5mgwnr7gioeus7|i-yeccrj5mgwnr7gioeycw|i-yeccrj5mgwnr7giohbib|i-yeccrj5mgwnr7gioj11t|i-yeccrj5mgwnr7giojlq3|i-yeccrj5mgwnr7giol75e|i-yeccrj5mgwnr7giom752|i-yeccrj5mgwnr7giooceo|i-yeccrj5mgwnr7gioot59|i-yeccrj5mgwnr7gioqv95|i-yeccrj5mgwnr7giormhg|i-yeccrj5mgwnr7giou7c3|i-yeccrj5mgwnr7giovrzg|i-yeccrj5mgwnr7giox59n|i-yeceez5tkw8lu7jmd7b6|i-yeceez5tkw8lu7jmfdj0|i-yeceez5tkw8lu7jmfu5x|i-yeceez5tkw8lu7jmgzex|i-yeceez5tkw8lu7jmjogm|i-yeceez5tkw8lu7jmkma8|i-yeceez5tkw8lu7jmlzd9|i-yeceez5tkw8lu7jmmn2v|i-yeceez5tkw8lu7jmp2fc|i-yeceez5tkw8lu7jmqm89|i-yeceez5tkw8lu7jms0uy|i-yeceez5tkw8lu7jms7mp|i-yeceez5tkw8lu7jmurwt|i-yeceez5tkw8lu7jmvr10|i-yeceez5tkw8lu7jmx7hg|i-yecs1xf8xssobos1fy2o|i-yecs1xf8xssobos1hwrp|i-yecs21zlds8lu7jgd671|i-yecs2frfuosobos34bxb|i-yecs38mw3k8lu7je7wz8|i-yecs38mw3k8lu7je9mao|i-yecu06d4w02kyw5rs7gl|i-yed2a8wkjk3z47guszu6|i-yed2a8wkjk3z47guub2e|i-yed2au1wcg8lu7j1a1sg|i-yed2au1wcg8lu7j1b4f3|i-yed2bqo7403z47gz1zf0|i-yed2bqo7403z47gz42u9|i-yed2bwycjksobosamt57|i-yed2mbnc3k2kyw5hdlhr|i-yed58zbnr4ajrd7iln30|i-yed9nnnv282kyw5gh5i6|i-yed9nnnv28sobos5qm89|i-yed9q2lgcg8lu7jqdt9r|i-yed9q2lgcgnr7gira8ax|i-yed9qeaups2kyw5fmbri|i-yeda4vxszk8lu7jb0wyt|i-yeda4vxszk8lu7jbm923|i-yeda55cbuo8lu7j3khsd|i-yeda55cbuosobos3a5ah|i-yedcpc7myo2kyw5gpro5|i-yedcpg9q0wsobos49n9t|i-yedd3ubg1s2kyw5lkutn|i-yeduxp71fksoborx1por|i-yedx3grocg3z47gdxxqp|i-yedxq93bwgnr7giammqp|i-yeedphp98gnr7giijjxx|i-yeedplep6onr7gickwbi|i-yeedplep6onr7giclwyv|i-yeenmmwhs0ajrd7jau37|i-yeenmmwhs0ajrd7jb9ht|i-yeenmmwhs0ajrd7jcqod|i-yeenmy2874ajrd7t7vpp|i-yeenmy2874ajrd7t9ezl|i-yeenmy2874ajrd7t9of2|i-yeenmy2874ajrd7tc0i1|i-yeenmy2874ajrd7tdla7|i-yeenmy2874ajrd7teo1w|i-yeenmy2874ajrd7tfwhp|i-yeenmy2874ajrd7tgna5|i-yeenmy2874ajrd7tirxu|i-yeenmy2874ajrd7tkeci|i-yeenmy2874ajrd7tl08h|i-yeenmy2874ajrd7tn3sa|i-yeenmy2874ajrd7to5ox|i-yeenmy2874ajrd7tq7pf|i-yeenmy2874ajrd7tr2x6|i-yeenmy2874ajrd7tsk9s|i-yeenmy2874ajrd7ttume|i-yeevnf4rnk2kyw5fkfkq|i-yeevnf4rnk2kyw5flgsg|i-yeew10cg008lu7jdr97q|i-yeew10cg008lu7jdt2qx|i-yeh1au677kajrd7wv2hm|i-yeh1au677kajrd7wx5z4|i-yeh1au677kajrd7wympw|i-yeh1au677kajrd7wzqfk|i-yeh1au677kajrd7x0ptx|i-yeh1au677kajrd7x21jw|i-yeh1au677kajrd7x3ew0|i-yeh1au677kajrd7x54yo|i-yeh1au677kajrd7x74jq|i-yeh1au677kajrd7x85g6|i-yeh1cgfd34nr7giiwup8|i-yeh1cgfd34nr7giix6u9|i-yeh1cgfd34nr7giiyst4|i-yeh1cgfd34nr7gij0q67|i-yeh1cgfd34nr7gij1gx0|i-yeh1cgfd34nr7gij3uhh|i-yeh1cgfd34nr7gij4ghb|i-yeh1cgfd34nr7gij66k9|i-yeh1cgfd34nr7gij8076|i-yeh1cgfd34nr7gij8py2|i-yeh1cgfd34nr7gij9ptf|i-yeh1cgfd34nr7gijb6xb|i-yeh1cgfd34nr7gijdju5|i-yeh1cgfd34nr7gijefpa|i-yeh1cgfd34nr7gijf5yl|i-yeh1cgfd34nr7gijhvk0|i-yeh1cgfd34nr7giji8oa|i-yeh1cgfd34nr7gijkpwu|i-yeh1cgfd34nr7gijl63p|i-yeh1cgfd34nr7gijn4rq|i-yeh1cgfd34nr7gijonl5|i-yeh1cgfd34nr7gijq543|i-yeh1cgfd34nr7gijrn8s|i-yeh1cgfd34nr7gijt316|i-yeh1cgfd34nr7giju2ak|i-yeh1cgfd34nr7gijvt62|i-yeh1cgfd34nr7gijwojz|i-yeh1cgfd34nr7gijxjbd|i-yeh1cgfd34nr7gijzc7y|i-yeh1cgfd34nr7gik1ex3|i-yeh1cggrnksoborzp01i|i-yeh1cggrnksoborzqi4l|i-yeh1cggrnksoborzript|i-yeh1cggrnksoborzsun1|i-yeh1cggrnksoborzv0t2|i-yeh1cggrnksoborzwmi0|i-yeh1cggrnksoborzxei3|i-yeh1cggrnksoborzzaij|i-yeh1cggrnksobos001fb|i-yeh1cggrnksobos029mk|i-yeh3xbyf408lu7j3kn7j)$/) AND time >= now() - 1h GROUP BY time(1m), "ResourceId", "DeviceName"'
}
data_cpu = {
    "q": 'SELECT max("value") FROM "Inner_CpuTotal" WHERE ("ResourceId" =~ /^(i-yeazlrqio0ajrd8213e7|i-yeazlrqio0ajrd821tz7|i-yeazlrqio0ajrd8242ff|i-yeazlrqio0ajrd824i36|i-yeazlu5lvk8lu7j7250l|i-yeazlu5lvk8lu7j73yf3|i-yeazlu5lvk8lu7j75t5o|i-yeazlu5lvk8lu7j76qj2|i-yeaznog4qonr7giml6c9|i-yeaznog4qonr7gimmq8b|i-yeaznog4qonr7gimnqu2|i-yeaznog4qonr7gimpr42|i-yeb41fdxxc8lu7jxop5l|i-yeb41fdxxc8lu7jxwwe6|i-yebclrmkg0nr7giitkve|i-yebu9ughs0nr7gji4qx0|i-yebuaa7z7knr7gij1ri3|i-yebuaa7z7knr7gij2mq5|i-yebuaa7z7knr7gij4hho|i-yebuaa7z7knr7gij5vt6|i-yebuaa7z7knr7gij7bef|i-yebubhgcg0ajrd7v7z0c|i-yebubhgcg0ajrd7v99sw|i-yebubhgcg0ajrd7vatzw|i-yebubhgcg0ajrd7vcmfy|i-yebubhgcg0ajrd7ven9i|i-yebubhgcg0ajrd7vfk8s|i-yebubhgcg0ajrd7vh1nw|i-yebubhgcg0ajrd7vhmeg|i-yebubhgcg0ajrd7vjbqv|i-yebubhgcg0ajrd7vlely|i-yebubhgcg0ajrd7vmw2m|i-yebubhgcg0ajrd7vnx2o|i-yebubhgcg0ajrd7voqv7|i-yebubhgcg0ajrd7vrabj|i-yebubhgcg0ajrd7vryya|i-yebubhgcg0ajrd7vtspz|i-yebubhgcg0ajrd7vve3k|i-yebubhgcg0ajrd7vwy0s|i-yebubhgcg0ajrd7vxbcq|i-yebubhgcg0ajrd7vz0az|i-yebubhgcg0ajrd7w0o3o|i-yebubhgcg0ajrd7w1a31|i-yebubhgcg0ajrd7w2xdd|i-yebubhgcg0ajrd7w50xv|i-yebubhgcg0ajrd7w6cwn|i-yebukfmnls8lu7jbk0hd|i-yebuuaqi2osoborzmamf|i-yebuuaqi2osoborzo4oq|i-yebuuaqi2osoborzozml|i-yebuuaqi2osoborzr4l9|i-yebuuaqi2osoborzsf7a|i-yebuuaqi2osoborztud3|i-yebuuaqi2osoborzu6pv|i-yebuuaqi2osoborzwav9|i-yebuuaqi2osoborzxv98|i-yebuuaqi2osoborzyjpz|i-yebuuaqi2osobos00hm3|i-yebuuaqi2osobos01yyn|i-yebuuaqi2osobos03iw2|i-yebuuaqi2osobos04ypn|i-yebuuaqi2osobos05do0|i-yebuuaqi2osobos07iyh|i-yebuuaqi2osobos090u5|i-yebuuaqi2osobos0a1ws|i-yebuuaqi2osobos0b6gd|i-yebuuaqi2osobos0cmbz|i-yebuuaqi2osobos0dydb|i-yebuuaqi2osobos0fwa1|i-yebuuaqi2osobos0hqje|i-yebuuaqi2osobos0i0yl|i-yebuuaqi2osobos0kdbk|i-yebuuaqi2osobos0li5g|i-yebuuaqi2osobos0nbur|i-yebuuaqi2osobos0oc35|i-yebuuaqi2osobos0pk4w|i-yebw7hpdz4nr7ginomyh|i-yebw7hpdz4nr7ginqj5y|i-yebw7hpdz4nr7ginr3xx|i-yebw7hpdz4nr7ginto00|i-yebw7hpdz4nr7ginupp4|i-yebw7hpdz4nr7ginw78p|i-yebw7hpdz4nr7ginxcz1|i-yebw7hpdz4nr7ginygrf|i-yebw7hpdz4nr7gio06d5|i-yebw7hpdz4nr7gio1jak|i-yebw7rf5dsnr7giqsff6|i-yebw7rf5dsnr7giqtjcp|i-yebw7rf5dsnr7giqun8a|i-yebw7rf5dsnr7giqwalz|i-yebw7rf5dsnr7giqx8nc|i-yebw7rf5dsnr7giqzf5l|i-yebw7rf5dsnr7gir10w7|i-yebw7rf5dsnr7gir1n3t|i-yebw7rf5dsnr7gir3ngx|i-yebw7rf5dsnr7gir4e42|i-yebw7rf5dsnr7gir5b5c|i-yebw7rf5dsnr7gir7l09|i-yebw7rf5dsnr7gir846h|i-yebw7rf5dsnr7giraqzk|i-yebw7rf5dsnr7giraynb|i-yebw7rf5dsnr7gircjsu|i-yebw7rf5dsnr7giredd8|i-yebw7rf5dsnr7girgcyt|i-yebw7rf5dsnr7girhla0|i-yebw7rf5dsnr7girj57i|i-yebw921q0w8lu7j1arbg|i-yebwbd5nnksobos4e08v|i-yebwbgighs3z47gk16p3|i-yebww2rdog3z47gfd2zc|i-yebww340sg3z47gfkbfp|i-yebwwavjswsoborxzfis|i-yebwwavjswsobory0v8y|i-yebwwavjswsobory28b5|i-yebwwavjswsobory3b6l|i-yebwwavjswsobory4pzj|i-yebwwavjswsobory6beo|i-yebwwavjswsobory7kv9|i-yebwwavjswsobory9364|i-yebwwavjswsoboryamrq|i-yebwwavjswsoborycav5|i-yebwwavjswsoborydptq|i-yebwwavjswsoboryeezk|i-yebwwavjswsoboryglbx|i-yebwwavjswsoboryhtgh|i-yebwwavjswsoboryinvb|i-yebwwavjswsoborykv4z|i-yebwwavjswsoborym28h|i-yebwwavjswsoborymxst|i-yebwwavjswsoboryolyg|i-yebwwbruv48lu7iynztn|i-yebwwbruv48lu7iyp663|i-yebwwbruv48lu7iyqru2|i-yebwwbruv48lu7iys9uw|i-yebwwbruv48lu7iytitw|i-yebwwbruv48lu7iyu7kk|i-yebwwbruv48lu7iyvltb|i-yebwwbruv48lu7iyxcuf|i-yebwwbruv48lu7iyxyuu|i-yebwwbruv48lu7iyzwle|i-yebwwbruv48lu7iz23zl|i-yebwwbruv48lu7iz2su5|i-yebwwbruv48lu7iz4hd4|i-yebwwbruv48lu7iz5uky|i-yebwwbruv48lu7iz715q|i-yebwwbruv48lu7iz8eoi|i-yebwwbruv48lu7iz9eez|i-yebwwbruv48lu7izaud2|i-yebwwbruv48lu7izcd88|i-yebx119pts3z47gwvmzk|i-yebx13negwnr7gicb0vt|i-yebx1895hc8lu7j3xbbx|i-yebx1895hc8lu7j3yiu0|i-yebx1895hc8lu7j3zhr9|i-yebx1cjny83z47genyu4|i-yebx5peewwajrd7e68zd|i-yebx5peewwajrd7e85wj|i-yebx5peewwajrd7e92jv|i-yebx5peewwajrd7ebeyk|i-yec1eri8sgnr7gicr5hg|i-yec1eri8sgnr7gicsddr|i-yec1eri8sgnr7gicuvoh|i-yec1esbqpsnr7gifis3i|i-yec1esbqpsnr7gifk9fm|i-yec1esbqpsnr7giflq85|i-yec4saes5c2kyw5vcmvs|i-yec4saes5c2kyw5veds0|i-yec4scd0jk3z47h1rx3a|i-yec4scd0jk3z47h1tfxx|i-yec4svehog2kyw5pvqcj|i-yec4svehog2kyw5py6oq|i-yec4svehog2kyw5pywc2|i-yec4svehog2kyw5q19qd|i-yec4svehog2kyw5q2eeu|i-yec4svehog2kyw5q2wd1|i-yec4tdmgw02kyw5jnnqk|i-yec4tdmgw02kyw5kmesm|i-yec4xkl43ksobosdksh0|i-yec4xkl43ksobosdnaic|i-yec4y8w7wgsobosdpcoz|i-yec4yaou0wnr7giafd33|i-yec4ycbtvk2kyw5coh7n|i-yec4ydt7ggnr7gii7f5r|i-yec4yindvksobosk7gge|i-yec4yindvksobosk94uz|i-yec56exrls3z47ggb9on|i-yec56exrls3z47ggbu68|i-yec56f905c8lu7j9jnas|i-yec56f905c8lu7j9karj|i-yec56fn1tssobos3eq5s|i-yec56fn1tssobos3fe61|i-yec56g13i88lu7jayh0c|i-yec56g13i88lu7jaykbe|i-yec56i7rb4soboryzoyi|i-yec56i7rb4soborz0wz5|i-yec56iq0ow3z47gztlhz|i-yec56iq0ow3z47gzuana|i-yec5d0wt8g3z47gmpe4j|i-yec5d0wt8g3z47gmqi87|i-yec5d0wt8g3z47gmruu4|i-yec5d0wt8g3z47gmtph8|i-yec5d1auww2kyw5l257d|i-yec5d1auww2kyw5l3psd|i-yec5d1auww2kyw5l4zwt|i-yec5d1auww2kyw5l6ld7|i-yec5d1owlcnr7gilgof7|i-yec5d1owlcnr7gilipj8|i-yec5d1owlcnr7giljrjo|i-yec5d1owlcnr7gill2dn|i-yec5d22y9snr7gimsnnl|i-yec5d22y9snr7gimubvw|i-yec5d22y9snr7gimvh4s|i-yec5d22y9snr7gimwlx9|i-yec75lwirknr7ginu0n5|i-yec75lwirknr7ginw069|i-yec75lwirknr7ginwupx|i-yec75n2nswnr7gin5rje|i-yec75n2nswnr7gin767l|i-yec75n2nswnr7gin8owc|i-yec9o2cd8gsoborx8lzb|i-yec9o2p0cgsobosc93i3|i-yec9o34glcajrd7k0n6u|i-yec9o3ii9ssoboryo1px|i-yecc94i7swsoboscda8i|i-yecc94i7swsoboscez5p|i-yecc94i7swsoboscgk5n|i-yecc98iwao3z47ghv229|i-yecc98iwao3z47ghvx9u|i-yeccrj5mgwnr7giocw47|i-yeccrj5mgwnr7gioeus7|i-yeccrj5mgwnr7gioeycw|i-yeccrj5mgwnr7giohbib|i-yeccrj5mgwnr7gioj11t|i-yeccrj5mgwnr7giojlq3|i-yeccrj5mgwnr7giol75e|i-yeccrj5mgwnr7giom752|i-yeccrj5mgwnr7giooceo|i-yeccrj5mgwnr7gioot59|i-yeccrj5mgwnr7gioqv95|i-yeccrj5mgwnr7giormhg|i-yeccrj5mgwnr7giou7c3|i-yeccrj5mgwnr7giovrzg|i-yeccrj5mgwnr7giox59n|i-yeceez5tkw8lu7jmd7b6|i-yeceez5tkw8lu7jmfdj0|i-yeceez5tkw8lu7jmfu5x|i-yeceez5tkw8lu7jmgzex|i-yeceez5tkw8lu7jmjogm|i-yeceez5tkw8lu7jmkma8|i-yeceez5tkw8lu7jmlzd9|i-yeceez5tkw8lu7jmmn2v|i-yeceez5tkw8lu7jmp2fc|i-yeceez5tkw8lu7jmqm89|i-yeceez5tkw8lu7jms0uy|i-yeceez5tkw8lu7jms7mp|i-yeceez5tkw8lu7jmurwt|i-yeceez5tkw8lu7jmvr10|i-yeceez5tkw8lu7jmx7hg|i-yecs1xf8xssobos1fy2o|i-yecs1xf8xssobos1hwrp|i-yecs21zlds8lu7jgd671|i-yecs2frfuosobos34bxb|i-yecs38mw3k8lu7je7wz8|i-yecs38mw3k8lu7je9mao|i-yecu06d4w02kyw5rs7gl|i-yed2a8wkjk3z47guszu6|i-yed2a8wkjk3z47guub2e|i-yed2au1wcg8lu7j1a1sg|i-yed2au1wcg8lu7j1b4f3|i-yed2bqo7403z47gz1zf0|i-yed2bqo7403z47gz42u9|i-yed2bwycjksobosamt57|i-yed2mbnc3k2kyw5hdlhr|i-yed58zbnr4ajrd7iln30|i-yed9nnnv282kyw5gh5i6|i-yed9nnnv28sobos5qm89|i-yed9q2lgcg8lu7jqdt9r|i-yed9q2lgcgnr7gira8ax|i-yed9qeaups2kyw5fmbri|i-yeda4vxszk8lu7jb0wyt|i-yeda4vxszk8lu7jbm923|i-yeda55cbuo8lu7j3khsd|i-yeda55cbuosobos3a5ah|i-yedcpc7myo2kyw5gpro5|i-yedcpg9q0wsobos49n9t|i-yedd3ubg1s2kyw5lkutn|i-yeduxp71fksoborx1por|i-yedx3grocg3z47gdxxqp|i-yedxq93bwgnr7giammqp|i-yeedphp98gnr7giijjxx|i-yeedplep6onr7gickwbi|i-yeedplep6onr7giclwyv|i-yeenmmwhs0ajrd7jau37|i-yeenmmwhs0ajrd7jb9ht|i-yeenmmwhs0ajrd7jcqod|i-yeenmy2874ajrd7t7vpp|i-yeenmy2874ajrd7t9ezl|i-yeenmy2874ajrd7t9of2|i-yeenmy2874ajrd7tc0i1|i-yeenmy2874ajrd7tdla7|i-yeenmy2874ajrd7teo1w|i-yeenmy2874ajrd7tfwhp|i-yeenmy2874ajrd7tgna5|i-yeenmy2874ajrd7tirxu|i-yeenmy2874ajrd7tkeci|i-yeenmy2874ajrd7tl08h|i-yeenmy2874ajrd7tn3sa|i-yeenmy2874ajrd7to5ox|i-yeenmy2874ajrd7tq7pf|i-yeenmy2874ajrd7tr2x6|i-yeenmy2874ajrd7tsk9s|i-yeenmy2874ajrd7ttume|i-yeevnf4rnk2kyw5fkfkq|i-yeevnf4rnk2kyw5flgsg|i-yeew10cg008lu7jdr97q|i-yeew10cg008lu7jdt2qx|i-yeh1au677kajrd7wv2hm|i-yeh1au677kajrd7wx5z4|i-yeh1au677kajrd7wympw|i-yeh1au677kajrd7wzqfk|i-yeh1au677kajrd7x0ptx|i-yeh1au677kajrd7x21jw|i-yeh1au677kajrd7x3ew0|i-yeh1au677kajrd7x54yo|i-yeh1au677kajrd7x74jq|i-yeh1au677kajrd7x85g6|i-yeh1cgfd34nr7giiwup8|i-yeh1cgfd34nr7giix6u9|i-yeh1cgfd34nr7giiyst4|i-yeh1cgfd34nr7gij0q67|i-yeh1cgfd34nr7gij1gx0|i-yeh1cgfd34nr7gij3uhh|i-yeh1cgfd34nr7gij4ghb|i-yeh1cgfd34nr7gij66k9|i-yeh1cgfd34nr7gij8076|i-yeh1cgfd34nr7gij8py2|i-yeh1cgfd34nr7gij9ptf|i-yeh1cgfd34nr7gijb6xb|i-yeh1cgfd34nr7gijdju5|i-yeh1cgfd34nr7gijefpa|i-yeh1cgfd34nr7gijf5yl|i-yeh1cgfd34nr7gijhvk0|i-yeh1cgfd34nr7giji8oa|i-yeh1cgfd34nr7gijkpwu|i-yeh1cgfd34nr7gijl63p|i-yeh1cgfd34nr7gijn4rq|i-yeh1cgfd34nr7gijonl5|i-yeh1cgfd34nr7gijq543|i-yeh1cgfd34nr7gijrn8s|i-yeh1cgfd34nr7gijt316|i-yeh1cgfd34nr7giju2ak|i-yeh1cgfd34nr7gijvt62|i-yeh1cgfd34nr7gijwojz|i-yeh1cgfd34nr7gijxjbd|i-yeh1cgfd34nr7gijzc7y|i-yeh1cgfd34nr7gik1ex3|i-yeh1cggrnksoborzp01i|i-yeh1cggrnksoborzqi4l|i-yeh1cggrnksoborzript|i-yeh1cggrnksoborzsun1|i-yeh1cggrnksoborzv0t2|i-yeh1cggrnksoborzwmi0|i-yeh1cggrnksoborzxei3|i-yeh1cggrnksoborzzaij|i-yeh1cggrnksobos001fb|i-yeh1cggrnksobos029mk|i-yeh3xbyf408lu7j3kn7j)$/ AND "value" > 5) AND time >= now() - 1h GROUP BY time(2s), "ResourceId" fill(linear) SLIMIT 30'
}
data_mem = {
    "q": 'SELECT max("value") FROM "Inner_MemoryUsedUtilization" WHERE ("ResourceId" =~ /^(i-yeazlrqio0ajrd8213e7|i-yeazlrqio0ajrd821tz7|i-yeazlrqio0ajrd8242ff|i-yeazlrqio0ajrd824i36|i-yeazlu5lvk8lu7j7250l|i-yeazlu5lvk8lu7j73yf3|i-yeazlu5lvk8lu7j75t5o|i-yeazlu5lvk8lu7j76qj2|i-yeaznog4qonr7giml6c9|i-yeaznog4qonr7gimmq8b|i-yeaznog4qonr7gimnqu2|i-yeaznog4qonr7gimpr42|i-yeb41fdxxc8lu7jxop5l|i-yeb41fdxxc8lu7jxwwe6|i-yebclrmkg0nr7giitkve|i-yebu9ughs0nr7gji4qx0|i-yebuaa7z7knr7gij1ri3|i-yebuaa7z7knr7gij2mq5|i-yebuaa7z7knr7gij4hho|i-yebuaa7z7knr7gij5vt6|i-yebuaa7z7knr7gij7bef|i-yebubhgcg0ajrd7v7z0c|i-yebubhgcg0ajrd7v99sw|i-yebubhgcg0ajrd7vatzw|i-yebubhgcg0ajrd7vcmfy|i-yebubhgcg0ajrd7ven9i|i-yebubhgcg0ajrd7vfk8s|i-yebubhgcg0ajrd7vh1nw|i-yebubhgcg0ajrd7vhmeg|i-yebubhgcg0ajrd7vjbqv|i-yebubhgcg0ajrd7vlely|i-yebubhgcg0ajrd7vmw2m|i-yebubhgcg0ajrd7vnx2o|i-yebubhgcg0ajrd7voqv7|i-yebubhgcg0ajrd7vrabj|i-yebubhgcg0ajrd7vryya|i-yebubhgcg0ajrd7vtspz|i-yebubhgcg0ajrd7vve3k|i-yebubhgcg0ajrd7vwy0s|i-yebubhgcg0ajrd7vxbcq|i-yebubhgcg0ajrd7vz0az|i-yebubhgcg0ajrd7w0o3o|i-yebubhgcg0ajrd7w1a31|i-yebubhgcg0ajrd7w2xdd|i-yebubhgcg0ajrd7w50xv|i-yebubhgcg0ajrd7w6cwn|i-yebukfmnls8lu7jbk0hd|i-yebuuaqi2osoborzmamf|i-yebuuaqi2osoborzo4oq|i-yebuuaqi2osoborzozml|i-yebuuaqi2osoborzr4l9|i-yebuuaqi2osoborzsf7a|i-yebuuaqi2osoborztud3|i-yebuuaqi2osoborzu6pv|i-yebuuaqi2osoborzwav9|i-yebuuaqi2osoborzxv98|i-yebuuaqi2osoborzyjpz|i-yebuuaqi2osobos00hm3|i-yebuuaqi2osobos01yyn|i-yebuuaqi2osobos03iw2|i-yebuuaqi2osobos04ypn|i-yebuuaqi2osobos05do0|i-yebuuaqi2osobos07iyh|i-yebuuaqi2osobos090u5|i-yebuuaqi2osobos0a1ws|i-yebuuaqi2osobos0b6gd|i-yebuuaqi2osobos0cmbz|i-yebuuaqi2osobos0dydb|i-yebuuaqi2osobos0fwa1|i-yebuuaqi2osobos0hqje|i-yebuuaqi2osobos0i0yl|i-yebuuaqi2osobos0kdbk|i-yebuuaqi2osobos0li5g|i-yebuuaqi2osobos0nbur|i-yebuuaqi2osobos0oc35|i-yebuuaqi2osobos0pk4w|i-yebw7hpdz4nr7ginomyh|i-yebw7hpdz4nr7ginqj5y|i-yebw7hpdz4nr7ginr3xx|i-yebw7hpdz4nr7ginto00|i-yebw7hpdz4nr7ginupp4|i-yebw7hpdz4nr7ginw78p|i-yebw7hpdz4nr7ginxcz1|i-yebw7hpdz4nr7ginygrf|i-yebw7hpdz4nr7gio06d5|i-yebw7hpdz4nr7gio1jak|i-yebw7rf5dsnr7giqsff6|i-yebw7rf5dsnr7giqtjcp|i-yebw7rf5dsnr7giqun8a|i-yebw7rf5dsnr7giqwalz|i-yebw7rf5dsnr7giqx8nc|i-yebw7rf5dsnr7giqzf5l|i-yebw7rf5dsnr7gir10w7|i-yebw7rf5dsnr7gir1n3t|i-yebw7rf5dsnr7gir3ngx|i-yebw7rf5dsnr7gir4e42|i-yebw7rf5dsnr7gir5b5c|i-yebw7rf5dsnr7gir7l09|i-yebw7rf5dsnr7gir846h|i-yebw7rf5dsnr7giraqzk|i-yebw7rf5dsnr7giraynb|i-yebw7rf5dsnr7gircjsu|i-yebw7rf5dsnr7giredd8|i-yebw7rf5dsnr7girgcyt|i-yebw7rf5dsnr7girhla0|i-yebw7rf5dsnr7girj57i|i-yebw921q0w8lu7j1arbg|i-yebwbd5nnksobos4e08v|i-yebwbgighs3z47gk16p3|i-yebww2rdog3z47gfd2zc|i-yebww340sg3z47gfkbfp|i-yebwwavjswsoborxzfis|i-yebwwavjswsobory0v8y|i-yebwwavjswsobory28b5|i-yebwwavjswsobory3b6l|i-yebwwavjswsobory4pzj|i-yebwwavjswsobory6beo|i-yebwwavjswsobory7kv9|i-yebwwavjswsobory9364|i-yebwwavjswsoboryamrq|i-yebwwavjswsoborycav5|i-yebwwavjswsoborydptq|i-yebwwavjswsoboryeezk|i-yebwwavjswsoboryglbx|i-yebwwavjswsoboryhtgh|i-yebwwavjswsoboryinvb|i-yebwwavjswsoborykv4z|i-yebwwavjswsoborym28h|i-yebwwavjswsoborymxst|i-yebwwavjswsoboryolyg|i-yebwwbruv48lu7iynztn|i-yebwwbruv48lu7iyp663|i-yebwwbruv48lu7iyqru2|i-yebwwbruv48lu7iys9uw|i-yebwwbruv48lu7iytitw|i-yebwwbruv48lu7iyu7kk|i-yebwwbruv48lu7iyvltb|i-yebwwbruv48lu7iyxcuf|i-yebwwbruv48lu7iyxyuu|i-yebwwbruv48lu7iyzwle|i-yebwwbruv48lu7iz23zl|i-yebwwbruv48lu7iz2su5|i-yebwwbruv48lu7iz4hd4|i-yebwwbruv48lu7iz5uky|i-yebwwbruv48lu7iz715q|i-yebwwbruv48lu7iz8eoi|i-yebwwbruv48lu7iz9eez|i-yebwwbruv48lu7izaud2|i-yebwwbruv48lu7izcd88|i-yebx119pts3z47gwvmzk|i-yebx13negwnr7gicb0vt|i-yebx1895hc8lu7j3xbbx|i-yebx1895hc8lu7j3yiu0|i-yebx1895hc8lu7j3zhr9|i-yebx1cjny83z47genyu4|i-yebx5peewwajrd7e68zd|i-yebx5peewwajrd7e85wj|i-yebx5peewwajrd7e92jv|i-yebx5peewwajrd7ebeyk|i-yec1eri8sgnr7gicr5hg|i-yec1eri8sgnr7gicsddr|i-yec1eri8sgnr7gicuvoh|i-yec1esbqpsnr7gifis3i|i-yec1esbqpsnr7gifk9fm|i-yec1esbqpsnr7giflq85|i-yec4saes5c2kyw5vcmvs|i-yec4saes5c2kyw5veds0|i-yec4scd0jk3z47h1rx3a|i-yec4scd0jk3z47h1tfxx|i-yec4svehog2kyw5pvqcj|i-yec4svehog2kyw5py6oq|i-yec4svehog2kyw5pywc2|i-yec4svehog2kyw5q19qd|i-yec4svehog2kyw5q2eeu|i-yec4svehog2kyw5q2wd1|i-yec4tdmgw02kyw5jnnqk|i-yec4tdmgw02kyw5kmesm|i-yec4xkl43ksobosdksh0|i-yec4xkl43ksobosdnaic|i-yec4y8w7wgsobosdpcoz|i-yec4yaou0wnr7giafd33|i-yec4ycbtvk2kyw5coh7n|i-yec4ydt7ggnr7gii7f5r|i-yec4yindvksobosk7gge|i-yec4yindvksobosk94uz|i-yec56exrls3z47ggb9on|i-yec56exrls3z47ggbu68|i-yec56f905c8lu7j9jnas|i-yec56f905c8lu7j9karj|i-yec56fn1tssobos3eq5s|i-yec56fn1tssobos3fe61|i-yec56g13i88lu7jayh0c|i-yec56g13i88lu7jaykbe|i-yec56i7rb4soboryzoyi|i-yec56i7rb4soborz0wz5|i-yec56iq0ow3z47gztlhz|i-yec56iq0ow3z47gzuana|i-yec5d0wt8g3z47gmpe4j|i-yec5d0wt8g3z47gmqi87|i-yec5d0wt8g3z47gmruu4|i-yec5d0wt8g3z47gmtph8|i-yec5d1auww2kyw5l257d|i-yec5d1auww2kyw5l3psd|i-yec5d1auww2kyw5l4zwt|i-yec5d1auww2kyw5l6ld7|i-yec5d1owlcnr7gilgof7|i-yec5d1owlcnr7gilipj8|i-yec5d1owlcnr7giljrjo|i-yec5d1owlcnr7gill2dn|i-yec5d22y9snr7gimsnnl|i-yec5d22y9snr7gimubvw|i-yec5d22y9snr7gimvh4s|i-yec5d22y9snr7gimwlx9|i-yec75lwirknr7ginu0n5|i-yec75lwirknr7ginw069|i-yec75lwirknr7ginwupx|i-yec75n2nswnr7gin5rje|i-yec75n2nswnr7gin767l|i-yec75n2nswnr7gin8owc|i-yec9o2cd8gsoborx8lzb|i-yec9o2p0cgsobosc93i3|i-yec9o34glcajrd7k0n6u|i-yec9o3ii9ssoboryo1px|i-yecc94i7swsoboscda8i|i-yecc94i7swsoboscez5p|i-yecc94i7swsoboscgk5n|i-yecc98iwao3z47ghv229|i-yecc98iwao3z47ghvx9u|i-yeccrj5mgwnr7giocw47|i-yeccrj5mgwnr7gioeus7|i-yeccrj5mgwnr7gioeycw|i-yeccrj5mgwnr7giohbib|i-yeccrj5mgwnr7gioj11t|i-yeccrj5mgwnr7giojlq3|i-yeccrj5mgwnr7giol75e|i-yeccrj5mgwnr7giom752|i-yeccrj5mgwnr7giooceo|i-yeccrj5mgwnr7gioot59|i-yeccrj5mgwnr7gioqv95|i-yeccrj5mgwnr7giormhg|i-yeccrj5mgwnr7giou7c3|i-yeccrj5mgwnr7giovrzg|i-yeccrj5mgwnr7giox59n|i-yeceez5tkw8lu7jmd7b6|i-yeceez5tkw8lu7jmfdj0|i-yeceez5tkw8lu7jmfu5x|i-yeceez5tkw8lu7jmgzex|i-yeceez5tkw8lu7jmjogm|i-yeceez5tkw8lu7jmkma8|i-yeceez5tkw8lu7jmlzd9|i-yeceez5tkw8lu7jmmn2v|i-yeceez5tkw8lu7jmp2fc|i-yeceez5tkw8lu7jmqm89|i-yeceez5tkw8lu7jms0uy|i-yeceez5tkw8lu7jms7mp|i-yeceez5tkw8lu7jmurwt|i-yeceez5tkw8lu7jmvr10|i-yeceez5tkw8lu7jmx7hg|i-yecs1xf8xssobos1fy2o|i-yecs1xf8xssobos1hwrp|i-yecs21zlds8lu7jgd671|i-yecs2frfuosobos34bxb|i-yecs38mw3k8lu7je7wz8|i-yecs38mw3k8lu7je9mao|i-yecu06d4w02kyw5rs7gl|i-yed2a8wkjk3z47guszu6|i-yed2a8wkjk3z47guub2e|i-yed2au1wcg8lu7j1a1sg|i-yed2au1wcg8lu7j1b4f3|i-yed2bqo7403z47gz1zf0|i-yed2bqo7403z47gz42u9|i-yed2bwycjksobosamt57|i-yed2mbnc3k2kyw5hdlhr|i-yed58zbnr4ajrd7iln30|i-yed9nnnv282kyw5gh5i6|i-yed9nnnv28sobos5qm89|i-yed9q2lgcg8lu7jqdt9r|i-yed9q2lgcgnr7gira8ax|i-yed9qeaups2kyw5fmbri|i-yeda4vxszk8lu7jb0wyt|i-yeda4vxszk8lu7jbm923|i-yeda55cbuo8lu7j3khsd|i-yeda55cbuosobos3a5ah|i-yedcpc7myo2kyw5gpro5|i-yedcpg9q0wsobos49n9t|i-yedd3ubg1s2kyw5lkutn|i-yeduxp71fksoborx1por|i-yedx3grocg3z47gdxxqp|i-yedxq93bwgnr7giammqp|i-yeedphp98gnr7giijjxx|i-yeedplep6onr7gickwbi|i-yeedplep6onr7giclwyv|i-yeenmmwhs0ajrd7jau37|i-yeenmmwhs0ajrd7jb9ht|i-yeenmmwhs0ajrd7jcqod|i-yeenmy2874ajrd7t7vpp|i-yeenmy2874ajrd7t9ezl|i-yeenmy2874ajrd7t9of2|i-yeenmy2874ajrd7tc0i1|i-yeenmy2874ajrd7tdla7|i-yeenmy2874ajrd7teo1w|i-yeenmy2874ajrd7tfwhp|i-yeenmy2874ajrd7tgna5|i-yeenmy2874ajrd7tirxu|i-yeenmy2874ajrd7tkeci|i-yeenmy2874ajrd7tl08h|i-yeenmy2874ajrd7tn3sa|i-yeenmy2874ajrd7to5ox|i-yeenmy2874ajrd7tq7pf|i-yeenmy2874ajrd7tr2x6|i-yeenmy2874ajrd7tsk9s|i-yeenmy2874ajrd7ttume|i-yeevnf4rnk2kyw5fkfkq|i-yeevnf4rnk2kyw5flgsg|i-yeew10cg008lu7jdr97q|i-yeew10cg008lu7jdt2qx|i-yeh1au677kajrd7wv2hm|i-yeh1au677kajrd7wx5z4|i-yeh1au677kajrd7wympw|i-yeh1au677kajrd7wzqfk|i-yeh1au677kajrd7x0ptx|i-yeh1au677kajrd7x21jw|i-yeh1au677kajrd7x3ew0|i-yeh1au677kajrd7x54yo|i-yeh1au677kajrd7x74jq|i-yeh1au677kajrd7x85g6|i-yeh1cgfd34nr7giiwup8|i-yeh1cgfd34nr7giix6u9|i-yeh1cgfd34nr7giiyst4|i-yeh1cgfd34nr7gij0q67|i-yeh1cgfd34nr7gij1gx0|i-yeh1cgfd34nr7gij3uhh|i-yeh1cgfd34nr7gij4ghb|i-yeh1cgfd34nr7gij66k9|i-yeh1cgfd34nr7gij8076|i-yeh1cgfd34nr7gij8py2|i-yeh1cgfd34nr7gij9ptf|i-yeh1cgfd34nr7gijb6xb|i-yeh1cgfd34nr7gijdju5|i-yeh1cgfd34nr7gijefpa|i-yeh1cgfd34nr7gijf5yl|i-yeh1cgfd34nr7gijhvk0|i-yeh1cgfd34nr7giji8oa|i-yeh1cgfd34nr7gijkpwu|i-yeh1cgfd34nr7gijl63p|i-yeh1cgfd34nr7gijn4rq|i-yeh1cgfd34nr7gijonl5|i-yeh1cgfd34nr7gijq543|i-yeh1cgfd34nr7gijrn8s|i-yeh1cgfd34nr7gijt316|i-yeh1cgfd34nr7giju2ak|i-yeh1cgfd34nr7gijvt62|i-yeh1cgfd34nr7gijwojz|i-yeh1cgfd34nr7gijxjbd|i-yeh1cgfd34nr7gijzc7y|i-yeh1cgfd34nr7gik1ex3|i-yeh1cggrnksoborzp01i|i-yeh1cggrnksoborzqi4l|i-yeh1cggrnksoborzript|i-yeh1cggrnksoborzsun1|i-yeh1cggrnksoborzv0t2|i-yeh1cggrnksoborzwmi0|i-yeh1cggrnksoborzxei3|i-yeh1cggrnksoborzzaij|i-yeh1cggrnksobos001fb|i-yeh1cggrnksobos029mk|i-yeh3xbyf408lu7j3kn7j)$/ AND "value" > 10) AND time >= now() - 1h GROUP BY time(2s), "ResourceId" fill(linear)'
}
# 定义 Webhook URL
webhook_url = 'https://open.larkoffice.com/open-apis/bot/v2/hook/783c6193-fb8d-4a2a-ab2c-c68d36ee0606'


def getdata(flag, top_n=1):
    # 使用 subprocess 调用 curl 命令
    try:
        if flag == 1:
                data_t = data_cpu
        elif flag == 2:
                data_t = data_mem
        elif flag == 3:
                data_t = data_disk
        else:
            print("没有找到有效的 CPU 使用率数据")
            return []
        
        response = requests.post(url, headers=headers, cookies=cookies, data=data_t)
        # 解析 JSON 响应 
        if response.status_code != 200:
            print(f"API 请求失败，状态码: {response.status_code}")
            return []
        
        # 初始化变量以追踪最高 CPU 使用率及其实例编号
        response_data = response.json()
        
        # 遍历每个系列
        if 'results' not in response_data or not response_data['results']:
            print("API 响应中没有 results 数据")
            return []
        
        if 'series' not in response_data['results'][0] or not response_data['results'][0]['series']:
            print("API 响应中没有 series 数据")
            return []
 
        # 初始化变量以追踪最高 CPU 使用率及其实例编号
        instance_usage = []

        # 遍历每个系列
        for series in response_data['results'][0]['series']:
            if 'tags' not in series or 'ResourceId' not in series['tags']:
                continue
            resource_id = series['tags']['ResourceId']
            #获取使用率值
            if 'values' not in series:
                continue
            max_instance_usage = float('-inf')
            for value in series['values']:
                if len(value) < 2:
                    continue
                usage = value[1]  
                #检查使用率是否为有效值
                if usage is not None and usage > max_instance_usage:
                    max_instance_usage = usage
            if max_instance_usage > float('-inf'):
                instance_usage.append((resource_id, max_instance_usage))

        instance_usage.sort(key=lambda x: x[1], reverse=True)
        
        top_instances = instance_usage[:top_n]

        if top_instances:
            if flag == 1:
                print("CPU 使用率最高的实例编号:")
            elif flag == 2:
                print("内存使用率最高的实例编号:")
            elif flag == 3:
                print("磁盘使用率最高的实例编号:")
            for i, (instance_id, usage) in enumerate(top_instances, 1):
                print(f"{i}. 实例ID: {instance_id}, 使用率: {usage}")
        else:
            print("没有符合条件的实例。")
        return top_instances


    except Exception as e:
        print(f"Error: {e}")
        return []

def send_msg(webhook_url, cpu_instances, mem_instances, disk_instances):
    #定义预警值
    maxusage_json = '''
    {
        "ecs": {
            "cpu_usage": 90,
            "mem_usage": 90,
            "disk_usage": 90
        }
    }
    '''
    #获取系统时间
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # 将 JSON 解析为 Python 字典
    maxusage = json.loads(maxusage_json)
    
    # 定义要推送的数据，使用变量插入实例 ID 和使用率
    cpu_content = "CPU 使用率:\n"
    for i, (instance_id, usage) in enumerate(cpu_instances, 1):
        color = 'red' if int(usage) >= maxusage['ecs']['cpu_usage'] else 'black'
        cpu_content += f"{i}. <font color='{color}'>{usage}%</font><text_tag color='blue'>实例ID:{instance_id}</text_tag>\n"
    
    # 定义要推送的数据，使用变量插入实例 ID 和使用率
    mem_content = "内存使用率:\n"
    for i, (instance_id, usage) in enumerate(mem_instances, 1):
        color = 'red' if int(usage) >= maxusage['ecs']['mem_usage'] else 'black'
        mem_content += f"{i}. <font color='{color}'>{usage}%</font><text_tag color='blue'>实例ID:{instance_id}</text_tag>\n"
    
    # 定义要推送的数据，使用变量插入实例 ID 和使用率
    disk_content = "磁盘使用率:\n"
    for i, (instance_id, usage) in enumerate(disk_instances, 1):
        color = 'red' if int(usage) >= maxusage['ecs']['disk_usage'] else 'black'
        disk_content += f"{i}. <font color='{color}'>{usage}%</font><text_tag color='blue'>实例ID:{instance_id}</text_tag>\n"
    
    # 组装推送数据
    data = {
    "msg_type": "interactive",
    "card": {
        "i18n_elements": {
        "zh_cn": [
            {
            "tag": "markdown",
            "content": ":GoGoGo:**ECS巡检结果** ",
            "text_align": "left",
            "text_size": "heading"
            },
            {
            "tag": "markdown",
            "content": cpu_content,
            "text_align": "left",
            "text_size": "normal"
            },
            {
            "tag": "markdown",
            "content": mem_content,
            "text_align": "left",
            "text_size": "normal"
            },
            {
            "tag": "column_set",
            "flex_mode": "none",
            "horizontal_spacing": "8px",
            "horizontal_align": "left",
            "columns": [
                {
                "tag": "column",
                "width": "weighted",
                "vertical_align": "top",
                "vertical_spacing": "8px",
                "elements": [
                    {
                    "tag": "markdown",
                    "content": disk_content,
                    "text_align": "left",
                    "text_size": "normal"
                    }
                ],
                "weight": 1
                }
            ],
            "margin": "16px 0px 0px 0px"
            },
            {
            "tag": "hr"
            }
        ]
        },
        "i18n_header": {
        "zh_cn": {
            "title": {
            "tag": "plain_text",
            "content": "得物：3000870176 ECS巡检"
            },
            "subtitle": {
            "tag": "plain_text",
            "content": f"整点播报：{current_time}"
            },
            "template": "orange",
            "ud_icon": {
            "tag": "standard_icon",
            "token": "approval_colorful"
            }
        }
        }
    }
    }
    #将数据发送到  Webhook
    response = requests.post(webhook_url, headers={"Content-Type": "application/json"}, data=json.dumps(data))

    # 检查请求是否成功
    if response.status_code == 200:
        print("推送成功")
    else:
        print(f"推送失败，状态码: {response.status_code}, 响应内容: {response.text}")

def wait_until_next_hour():
    now = datetime.now()
    # 计算下一个整点时间
    next_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    # 计算当前时间到下一个整点的秒数
    seconds_until_next_hour = (next_hour - now).total_seconds()
    print("Sleep: \n", seconds_until_next_hour)
    time.sleep(seconds_until_next_hour)


@dataclass(frozen=True)
class Constants:
    CPU_f: int = 1
    MEM_f: int = 2
    DISK_f: int = 3

while True:
    # 等待到下一个整点
    #wait_until_next_hour()
    flag = Constants.CPU_f #CPU
    cpu_instances = getdata(flag, top_n=3)  # 获得CPU使用率最高的3个实例

    flag = 2 #内存
    mem_instances = getdata(flag, top_n=3)  # 获得内存使用率最高的3个实例

    flag = 3 #磁盘
    disk_instances = getdata(flag, top_n=3)  # 获得磁盘使用率最高的3个实例

    #推送飞书机器人卡片
    send_msg(webhook_url, cpu_instances, mem_instances, disk_instances)
    # 等待到下一个整点
    wait_until_next_hour()
