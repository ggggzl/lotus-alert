#!/usr/bin/env python3
#########################################################################
# 本脚本用于FileCoin日常巡检，及时告警通知到企业微信。
# FilGuard致力于提供开箱即用的Fil挖矿技术解决方案
# 如有问题联系脚本作者「mje」：
# WeChat：Mjy_Dream
#########################################################################

from __future__ import print_function
import time
import json
import re
import sys
import traceback
import subprocess as sp
from datetime import datetime
import requests

# Server酱SendKey「必填，填写为自己的SendKey」
send_key = "SCT42628TJaSP3AraKD0Hua6Woxiaxiede"
# 可配置Server酱推送到企业微信中特定人或多个人「选填，具体可参考文档」
openid = "yingtaoxiaowanzi|mje"
# 脚本运行所在的机器类型
# lotus（一）、Seal-Miner（二）、Wining-Miner（三）、WindowPost-Miner（四）
# 现做出约定，直接填写一、二、三、四来表示对应的机器类型，可写入多个类型
check_machine = "一二三四"
# 需要进行服务器宕机/网络不可达检验的内网ip，以|号分割
server_ip = "192.168.100.5|192.168.100.6|192.168.100.99"
# ssh 登录授权IP地址,以|号分割，如果登录IP不在列表中，将发出告警消息。
ssh_white_ip_list = "192.168.85.10|221.10.1.1"
# 存储挂载路径「选填，在Seal-Miner、Wining-Miner、WindowPost-Miner上运行时需要填写，多个挂载目录使用'|'进行分隔」
file_mount = "/fcfs"
# WindowPost—Miner日志路径「选填，在WindowPost-Miner上运行时需要填写」
wdpost_log_path = "/home/filguard/miner.log"
# WiningPost-Miner日志路径「选填，在Wining-Miner上运行时需要填写」
winingpost_log_path = "/home/filguard/miner.log"
# fil_account 为你的Miner节点号「必填，用于爆块检测」
fil_account = "f099（黑洞）"
# 最长时间任务告警，如设置10，那么sealing jobs中最长的时间超过10小时就会告警「选填」
job_time_alert = 10
# Default钱包余额告警阈值「选填，默认50」
default_wallet_balance = 50
# check_interval 程序循环检查间隔默认300秒
check_interval = 300


def print(s, end='\n', file=sys.stdout):
    file.write(s + end)
    file.flush()

def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        pass
 
    try:
        import unicodedata
        unicodedata.numeric(s)
        return True
    except (TypeError, ValueError):
        pass
    return False

def server_post(title='默认标题',content='默认正文'):
    global send_key
    global fil_account
    global openid
    api = "https://sctapi.ftqq.com/" + send_key + ".send"
    data = {
        "text":(fil_account+":"+title),
        "desp":content,
        "openid":openid
    }
    try:
        req = requests.post(api,data = data)
        req_json = json.loads(req.text)
        if req_json.get("data").get("errno") == 0:
            print("server message sent successfully: " + title + " | " + content)
            return True
        else:
            print("server message sent failed: " + req.text)
            return False
    except requests.exceptions.RequestException as req_error:
        print("Request error: "+req_error)
    except Exception as e:
        print("Fail to send message: " + e)

def init_check():
    try:
        #初始化目前日志中的爆块数量
        if check_machine.find('三')>=0:
            global block_count
            out = sp.getoutput("cat "+ winingpost_log_path +" | grep 'mined new block' | wc -l")
            block_count = int(out)
    except KeyboardInterrupt:
        exit(0)
    except:
        traceback.print_exc()
        time.sleep(10)
        
# 高度同步检查
def chain_check():
    try:
        out = sp.getoutput("timeout 36s lotus sync wait")
        print('chain_check:')
        print(out)
        if  out.endswith('Done!'):
            print("true")
            return True
        server_post("节点同步出错","请及时排查！")
        return False
    except Exception as e:
        print("Fail to send message: " + e)
    
# 显卡驱动检查
def nvidia_check(check_type=''):
    out = sp.getoutput("timeout 30s echo $(nvidia-smi | grep GeForce)")
    print('nvidia_check:')
    print(out)
    if out.find("GeForce")>=0:
        print("true")
        return True
    server_post(check_type,"显卡驱动故障，请及时排查！")
    return False

# miner进程检查
def minerprocess_check(check_type=''):
    out = sp.getoutput("timeout 30s echo $(pidof lotus-miner)")
    print('minerprocess_check:')
    print(out)
    if out.strip():
        print("true")
        return True
    server_post(check_type,"Miner进程丢失，请及时排查！")
    return False

# lotus进程检查
def lotusprocess_check():
    out = sp.getoutput("timeout 30s echo $(pidof lotus)")
    print('lotusprocess_check:')
    print(out)
    if out.strip():
        print("true")
        return True
    server_post("Lotus","Lotus进程丢失，请及时排查！")
    print("false")
    return False

# 消息堵塞检查
def mpool_check():
    out = sp.getoutput("lotus mpool pending --local | wc -l")
    print('mpool_check:')
    print(out)
    if is_number(out):
        if int(out)<=240:
            print("true")
            return True
        server_post("Lotus","消息堵塞，请及时清理！") 
    return False

# 存储文件挂载检查
def fm_check(check_type=''):
    global file_mount
    fs = file_mount.split('|')
    for str in fs:
        out = sp.getoutput("timeout 30s echo $(df -h | grep "+ str +")")
        print('fm_check:')
        print(out)
        if not out.strip():
            print("false")
            server_post(check_type,"未发现存储挂载目录，请及时排查！")
            return False
    return True

# WindowPost—Miner日志报错检查
def wdpost_log_check():
    out = sp.getoutput("cat "+ wdpost_log_path +"| grep 'running window post failed'")
    print('wdpost_log_check:')
    print(out)
    if not out.strip():
        print("true")
        return True
    server_post("WindowPost","Wdpost报错，请及时处理！")
    return False

# WiningPost—Miner爆块检查
def mined_block_check():
    mined_block_cmd = "lotus chain list --count {0} |grep {1} |wc -l".format(int(check_interval/30), fil_account)
    out = sp.getoutput(mined_block_cmd)
    print('mined_block_check:')
    print(out)
    block_count=int(out)
    if block_count > 0:
        print("true")
        server_post("{0}又爆了{1}个块".format(fil_account, block_count),"大吉大利，今晚吃鸡")
        return True
    return False

# 任务超时检查
def overtime_check():
    global job_time_alert
    out = sp.getoutput("lotus-miner sealing jobs | awk '{ print $7}' | head -n 2 | tail -n 1")
    print('overtime_check:')
    print(out)
    if (out.find("Time")>=0) or (not out.find('h')>=0):
        print("time true")
        return True
    if out.strip() and int(out[0:out.find('h')])<=job_time_alert:
        print(out[0:out.find("h")])
        print("true")
        return True
    server_post("SealMiner","封装任务超时，请及时处理！")
    return False

# Default钱包余额预警
def balance_check():
    global default_wallet_balance
    out = sp.getoutput("lotus wallet balance")
    print('balance_check:')
    print(out)
    balance = out.split(' ')
    if is_number(balance[0]):
        if float(balance[0])<default_wallet_balance:
            print("false")
            server_post("Lotus","钱包余额不足，请及时充值！")
            return False
    return True

# 检查服务器是否可达（宕机或网络不通）
def reachable_check():
    try:
        global server_ip
        is_reachable = True
        ips = server_ip.split('|')
        print('reachable_check:')
        for ip in ips:
            print(ip)    
            p = sp.Popen(["ping -c 1 -W 1 "+ ip],stdout=sp.PIPE,stderr=sp.PIPE,shell=True)
            out=p.stdout.read()
            regex=re.compile('100% packet loss')
            if len(regex.findall(str(out))) != 0:
                print("false")
                server_post(str(ip),"服务器不可达（宕机/网络故障），请及时排查！")
                is_reachable = False  
        return is_reachable
    except:
        print('reachable_check error!')

# ssh 登录IP是否授权检查
def ssh_login_ip_check():
    try:
        global ssh_white_ip_list
        print("ssh logined ip check:\n")
        hostname = sp.getoutput("hostname")
        #获取已登录用户IP地址列表
        out = sp.getoutput("who |grep -v tmux |awk '{print $5}'")
        out = out.replace("(","").replace(")","")
        login_ip_list = out.split('\n')
        #去除重复
        login_ip_list = set(login_ip_list)
        login_ip_list = list(login_ip_list)
        #把ssh登录授权IP地址格式化成列表
        ssh_white_ip_list = ssh_white_ip_list.split('|')
        #检测已登录IP是否授权
        for ip in login_ip_list:
            if ip != "" and ip not in ssh_white_ip_list:
                curtime = time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(time.time()))
                msg = "{0},未授权IP:{1},已登录服务器{2}".format(curtime, ip, hostname)
                server_post(hostname,msg)
        print("--------ssh logined ip check finished -------------")   
    except Exception as e:
        print(str(e))

def loop():
    while True:
        try:
            global check_machine
            global fil_account
            if not check_machine.strip():
                print("请填写巡检的机器类型！")
                break
            if reachable_check():
                print("各服务器均可达，无异常")
            if check_machine.find('一')>=0:
                if lotusprocess_check():
                    if chain_check():
                        balance_check()
                        if mpool_check():
                            print("---------------------")
                            print(time.asctime(time.localtime(time.time())))
                            print("Lotus已巡检完毕，无异常")
            if check_machine.find('二')>=0:
                if minerprocess_check("SealMiner") and fm_check("SealMiner") and overtime_check():
                    print("---------------------")
                    print(time.asctime(time.localtime(time.time())))
                    print("Seal-Miner已巡检完毕，无异常")   
            if check_machine.find('三')>=0:
                mined_block_check()
                if nvidia_check("WiningMiner") and minerprocess_check("WiningMiner") and fm_check("WiningMiner"):
                    print("---------------------")
                    print(time.asctime(time.localtime(time.time())))
                    print("WiningPost-Miner已巡检完毕，无异常")                
            if check_machine.find('四')>=0:
                if nvidia_check("WindowPostMiner") and minerprocess_check("WindowPostMiner") and fm_check("WindowPostMiner") and wdpost_log_check():
                    print("---------------------")
                    print(time.asctime(time.localtime(time.time())))    
                    print("WindowPost-Miner已巡检完毕，无异常") 
            # sleep
            print("sleep {0} seconds\n".format(check_interval))
            time.sleep(check_interval)
        except KeyboardInterrupt:
            exit(0)
        except:
            traceback.print_exc()
            time.sleep(120)

def main():
    loop()

if __name__ == "__main__":
    init_check()
    main()

