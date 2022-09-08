#!/usr/bin/env python3
# -*- coding: utf-8 -*-q

from djitellopy import Tello    # DJITelloPyのTelloクラスをインポート
import time                     # time.sleepを使いたいので
import cv2                      # OpenCVを使うため
import numpy as np              # ラベリングにNumPyが必要なので

from hsvColor import hsv_color

# Telloクラスを使って，tellというインスタンス(実体)を作る
tello = Tello(retry_count=1)

def labeling(bgr_image, color_code='R'):

    hsv_image = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2HSV)  # BGR画像 -> HSV画像

    #認識する色のhsvを取得（デフォルトは赤）
    hsv_min, hsv_max = hsv_color(color_code)

    # inRange関数で範囲指定２値化
    bin_image = cv2.inRange(hsv_image, hsv_min, hsv_max)        # HSV画像なのでタプルもHSV並び
    kernel = np.ones((15,15),np.uint8)  # 15x15で膨張させる
    bin_image = cv2.dilate(bin_image,kernel,iterations = 1)    # 膨張して虎ロープをつなげる

    # bitwise_andで元画像にマスクをかける -> マスクされた部分の色だけ残る
    result_image = cv2.bitwise_and(hsv_image, hsv_image, mask=bin_image)   # HSV画像 AND HSV画像 なので，自分自身とのANDは何も変化しない->マスクだけ効かせる

    # 面積・重心計算付きのラベリング処理を行う
    num_labels, label_image, stats, center = cv2.connectedComponentsWithStats(bin_image)

    # 最大のラベルは画面全体を覆う黒なので不要．データを削除
    num_labels = num_labels - 1
    stats = np.delete(stats, 0, 0)
    center = np.delete(center, 0, 0)

    return result_image, num_labels, label_image, stats, center

#####################   linetrace()   ##########################
#
#   引数
#   small_image:    telloが取得したオリジナル画像（size 480*360）
#   auto_mode:      telloの現在の状態
#   color_code:     認識したい色(R=赤, B=青, G=緑)
#
#   戻り値
#   result_image:   画像処理後の画像
#   auto_mode:      telloの現在の状態（完了したら状態は'land'
#                                    になります)
#
###############################################################

#終点かどうかのフラグ
traceing = 0
terminus = 0

#高度を調整するためのフラグ
linetrace_fg = 0

def linetrace(small_image, auto_mode=None, color_code='R'):

    global terminus, traceing, linetrace_fg

    #ドローンの高さ
    Drone_hight = 10

    result_image, num_labels, label_image, stats, center = labeling(small_image[250:359,0:479], color_code='R')

    #ドローンの高さを10に設定
    if linetrace_fg == 0:
        state = tello.get_current_state()
        if not state['h'] == Drone_hight:
            time.sleep(3)
            tello.send_rc_control( 0, 0, Drone_hight - state['h'], 0 )
            time.sleep(3)
        state = tello.get_current_state()
        print(f"Drone hight is {state['h']} (expect:{Drone_hight})")
        linetrace_fg = 1

    #トレーシングを100フレーム行った後にラベルが0になったらカウント
    if num_labels < 1 and traceing > 100:
        terminus += 1

    if num_labels >= 1:
        #トレースを行っているかのカウント
        traceing += 1
        # 面積最大のインデックスを取得
        max_index = np.argmax(stats[:,4])
        #print max_index

        # 面積最大のラベルのx,y,w,h,面積s,重心位置mx,myを得る
        x = stats[max_index][0]
        y = stats[max_index][1]
        w = stats[max_index][2]
        h = stats[max_index][3]
        s = stats[max_index][4]
        mx = int(center[max_index][0])
        my = int(center[max_index][1])
        #print("(x,y)=%d,%d (w,h)=%d,%d s=%d (mx,my)=%d,%d"%(x, y, w, h, s, mx, my) )

        # ラベルを囲うバウンディングボックスを描画
        cv2.rectangle(result_image, (x, y), (x+w, y+h), (255, 0, 255))

        # 重心位置の座標と面積を表示
        cv2.putText(result_image, "%d,%d"%(mx,my), (x-15, y+h+15), cv2.FONT_HERSHEY_PLAIN, 1, (255, 255, 0))
        cv2.putText(result_image, "%d"%(s), (x, y+h+30), cv2.FONT_HERSHEY_PLAIN, 1, (255, 255, 0))

        if auto_mode == 'linetrace':
            a = b = c = d = 0
            b=30

            # 制御式(ゲインは低めの0.3)
            dx = 0.4 * (240 - mx)       # 画面中心との差分

            # 旋回方向の不感帯を設定
            d = 0.0 if abs(dx) < 10.0 else dx   # ±50未満ならゼロにする

            # 旋回方向のソフトウェアリミッタ(±100を超えないように)
            d =  100 if d >  100.0 else d
            d = -100 if d < -100.0 else d

            d = -d   # 旋回方向が逆だったので符号を反転

            #print('dx=%f'%(dx) )
            tello.send_rc_control( int(a), int(b), int(c), int(d) )

    #ターミナルポイントに50フレーム以上いた場合着地モードに移行
    if terminus > 50 and not auto_mode == 'manual':
        tello.send_rc_control( 0, 0, 0, 0 )
        time.sleep(3)
        tello.rotate_counter_clockwise(90)
        time.sleep(3)
        auto_mode = 'land'

    return result_image, auto_mode

def main():
    # 初期化部
    # Telloクラスを使って，tellというインスタンス(実体)を作る
    tello = Tello(retry_count=1)    # 応答が来ないときのリトライ回数は1(デフォルトは3)
    tello.RESPONSE_TIMEOUT = 0.01   # コマンド応答のタイムアウトは短くした(デフォルトは7)

    # Telloへ接続
    tello.connect()

    # 画像転送を有効にする
    tello.streamoff()   # 誤動作防止の為、最初にOFFする
    tello.streamon()    # 画像転送をONに
    frame_read = tello.get_frame_read()     # 画像フレームを取得するBackgroundFrameReadクラスのインスタンスを作る

    current_time = time.time()  # 現在時刻の保存変数
    pre_time = current_time     # 5秒ごとの'command'送信のための時刻変数

    motor_on = False                    # モータON/OFFのフラグ
    camera_dir = Tello.CAMERA_FORWARD   # 前方/下方カメラの方向のフラグ

    # トラックバーを作るため，まず最初にウィンドウを生成
    cv2.namedWindow("OpenCV Window")

    # 自動モードフラグ
    auto_mode = 'manual'

    time.sleep(0.5)     # 通信が安定するまでちょっと待つ

    # ループ部
    # Ctrl+cが押されるまでループ
    try:
        # 永久ループで繰り返す
        while True:

            # (A) 画像取得
            image = frame_read.frame    # 映像を1フレーム取得しimage変数に格納

            # (B) 画像サイズ変更と、カメラ方向による回転
            small_image = cv2.resize(image, dsize=(480,360) )   # 画像サイズを半分に変更

            if camera_dir == Tello.CAMERA_DOWNWARD:     # 下向きカメラは画像の向きが90度ずれている
                small_image = cv2.rotate(small_image, cv2.ROTATE_90_CLOCKWISE)      # 90度回転して、画像の上を前方にする

            # (C) ここから画像処理

            #ライントレース
            result_image, auto_mode = linetrace(small_image, auto_mode, color_code)
            if auto_mode == 'land':
                print("======== Done Linetrace =======")
                auto_mode = 'manual'

            # (X) ウィンドウに表示
            cv2.imshow('OpenCV Window', result_image)    # ウィンドウに表示するイメージを変えれば色々表示できる
            #cv2.imshow('Binary Image', bin_image)
            cv2.imshow('defo Image', small_image)

            # (Y) OpenCVウィンドウでキー入力を1ms待つ
            key = cv2.waitKey(1) & 0xFF
            if key == 27:                   # key が27(ESC)だったらwhileループを脱出，プログラム終了
                break
            elif key == ord('t'):           # 離陸
                tello.takeoff()
            elif key == ord('l'):           # 着陸
                tello.send_rc_control( 0, 0, 0, 0 )
                tello.land()
            elif key == ord('w'):           # 前進 30cm
                tello.move_forward(30)
            elif key == ord('s'):           # 後進 30cm
                tello.move_back(30)
            elif key == ord('a'):           # 左移動 30cm
                tello.move_left(30)
            elif key == ord('d'):           # 右移動 30cm
                tello.move_right(30)
            elif key == ord('e'):           # 旋回-時計回り 30度
                tello.rotate_clockwise(30)
            elif key == ord('q'):           # 旋回-反時計回り 30度
                tello.rotate_counter_clockwise(30)
            elif key == ord('r'):           # 上昇 30cm
                tello.move_up(30)
            elif key == ord('f'):           # 下降 30cm
                tello.move_down(30)
            elif key == ord('p'):           # ステータスをprintする
                print(tello.get_current_state())
            elif key == ord('m'):           # モータ始動/停止を切り替え
                if motor_on == False:       # 停止中なら始動
                    tello.turn_motor_on()
                    motor_on = True
                else:                       # 回転中なら停止
                    tello.turn_motor_off()
                    motor_on = False
            elif key == ord('c'):           # カメラの前方/下方の切り替え
                if camera_dir == Tello.CAMERA_FORWARD:     # 前方なら下方へ変更
                    tello.set_video_direction(Tello.CAMERA_DOWNWARD)
                    camera_dir = Tello.CAMERA_DOWNWARD     # フラグ変更
                else:                                      # 下方なら前方へ変更
                    tello.set_video_direction(Tello.CAMERA_FORWARD)
                    camera_dir = Tello.CAMERA_FORWARD      # フラグ変更
                time.sleep(0.5)     # 映像が切り替わるまで少し待つ
            elif key == ord('1'):
                auto_mode = 'linetrace'                    # 追跡モードON
            elif key == ord('0'):
                tello.send_rc_control( 0, 0, 0, 0 )
                auto_mode = 'manual'                    # 追跡モードOFF

            # (Z) 10秒おきに'command'を送って、死活チェックを通す
            current_time = time.time()                          # 現在時刻を取得
            if current_time - pre_time > 10.0 :                 # 前回時刻から10秒以上経過しているか？
                tello.send_command_without_return('command')    # 'command'送信
                pre_time = current_time                         # 前回時刻を更新

    except( KeyboardInterrupt, SystemExit):    # Ctrl+cが押されたらループ脱出
        print( "Ctrl+c を検知" )

    # 終了処理部
    tello.send_rc_control( 0, 0, 0, 0 )
    cv2.destroyAllWindows()                             # すべてのOpenCVウィンドウを消去
    tello.set_video_direction(Tello.CAMERA_FORWARD)     # カメラは前方に戻しておく
    tello.streamoff()                                   # 画像転送を終了(熱暴走防止)
    frame_read.stop()                                   # 画像受信スレッドを止める

    del tello.background_frame_read                    # フレーム受信のインスタンスを削除
    del tello                                           # telloインスタンスを削除

# "python3 main_linetrace.py"として実行された時だけ動く様にするおまじない処理
if __name__ == "__main__":      # importされると__name_に"__main__"は入らないので，pyファイルが実行されたのかimportされたのかを判断できる．
    #認識したい色を設定(R=赤, B=青, G=緑)
    color_code = 'R'
    main()    # メイン関数を実行
