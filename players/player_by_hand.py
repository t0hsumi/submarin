import json
import os
import random
import socket
import sys

sys.path.append(os.getcwd())

from lib.player_base import Player, PlayerShip


class PlayerByHand(Player):

    def __init__(self, seed=0):
        random.seed(seed)

        # 初期のフィールドを配列として持っておく
        self.field = [[i, j] for i in range(Player.FIELD_SIZE)
                             for j in range(Player.FIELD_SIZE)]

        # 初期配置は広い範囲を攻撃できる場所に変更する。
        positions = {'w': [1,1], 'c': [3,2], 's': [1,3]}

        # 敵の候補地点として考えられるもの全て
        self.enemy_positions = {'w':[[i, j] for i in range(Player.FIELD_SIZE)
                                     for j in range(Player.FIELD_SIZE)],
                                'c':[[i, j] for i in range(Player.FIELD_SIZE)
                                     for j in range(Player.FIELD_SIZE)],
                                's':[[i, j] for i in range(Player.FIELD_SIZE)
                                     for j in range(Player.FIELD_SIZE)]}
        # 敵の現在のHP
        self.enemy_hp = {'w': 3, 'c': 2, 's': 1}

        # feedbackが自分のした攻撃によるものであるかどうか
        self.have_attacked = False
        super().__init__(positions)

    # 攻撃してnearとなった場合の敵位置の更新
    def attack_near_update(self, near_target, attack_point):
        possible_point = [[attack_point[0]+i, attack_point[1]+j]
                for i in range(-1, 2) for j in range(-1, 2) if not (i==0 and j==0)]
        for enemy in ['w', 'c', 's']:
            # もう候補が一つの場合は絞る必要なし
            # これは、hitし、かつ、nearが存在する場合のコンフリクトを避けている
            if len(self.enemy_positions[enemy]) == 1:
                continue

            # nearに引っかかった場合多くとも8通りに絞られる
            elif enemy in near_target:
                update_position = []
                for point in possible_point:
                    if point in self.enemy_positions[enemy]:
                        update_position.append(point)
                self.enemy_positions[enemy] = update_position

            # hitもせずnearに引っかからなかった場合9か所除外できる
            else:
                update_position = []
                for point in self.enemy_positions[enemy]:
                    if point not in possible_point and point != attack_point:
                        update_position.append(point)
                self.enemy_positions[enemy] = update_position

    # 敵からの攻撃による敵位置の更新
    def enemy_attack_update(self, attack_point):
        possible_point = [[attack_point[0]+i, attack_point[1]+j]
                            for i in range(-1, 2) for j in range(-1, 2)]
        for enemy in ['w', 'c', 's']:
            update_position = []
            for point in self.enemy_positions[enemy]:
                if point in possible_point:
                    update_position.append(point)
            self.enemy_positions[enemy] += update_position

    # 敵が移動した場合
    # 元々考えられていた候補の中を更新し、あり得ないものを除外する
    def enemy_movement_update(self, move_enemy, direction):
        update_position = []
        for point in self.enemy_positions[move_enemy]:
            move_to = [pos + direc for (pos, direc) in zip(point, direction)]
            if move_to[0] < super().FIELD_SIZE and move_to[1] < super().FIELD_SIZE \
                    and move_to[0] >= 0 and move_to[1] >= 0:
                update_position.append(move_to)
        self.enemy_positions[move_enemy] = update_position

    # 自分が攻撃した場合のフィードバック
    def my_attack_update(self, cond):
        attack_point = cond['result']['attacked']['position']
        # 自分の攻撃が当たった場合
        if 'hit' in cond['result']['attacked']:
            is_attacked_enemy = cond['result']['attacked']['hit']
            self.enemy_positions[is_attacked_enemy] = [attack_point]
            self.enemy_hp[is_attacked_enemy] -= 1

        # 自分の攻撃箇所の近くに敵がいた場合
        if 'near' in cond['result']['attacked']:
            self.attack_near_update(cond['result']['attacked']['near'], attack_point)
        self.have_attacked = False

    # json形式で与えられたfeedbackを反映する
    def update(self, json_):
        cond = json.loads(json_)

        # 自分の攻撃のフィードバック
        if self.have_attacked:
            self.my_attack_update(cond)

        # 敵の行動のフィードバック
        elif 'result' in cond:
            if 'attacked' in cond['result']:
                self.enemy_attack_update(cond['result']['attacked']['position'])
            if 'moved' in cond['result']:
                self.enemy_movement_update(cond['result']['moved']['ship'],
                                           cond['result']['moved']['distance'])
        super().update(json_)

    def attack_to_random_point(self):
        # フィールドを2x2の配列として持っている．
        field = [[i, j] for i in range(Player.FIELD_SIZE)
                        for j in range(Player.FIELD_SIZE)]
        to = random.choice(field)
        while not super().can_attack(to):
            to = random.choice(field)
        return json.dumps(self.attack(to))

    def attack_in_field(self, field):
        to = random.choice(field)
        while not super().can_attack(to):
            to = random.choice(field)
        self.have_attacked = True
        return json.dumps(self.attack(to))

    # ある敵に攻撃可能かどうか調べる関数
    def is_in_range(self, enemy):
        for point in self.enemy_positions[enemy]:
            if super().can_attack(point):
                return True
        return False

    #
    # 可能性があるうち最も小さいものをさらに絞っていく。
    #
    def action(self):
        # 敵とその敵が存在しうる場所の数をpossibilitiesに入れる。
        possibilities = {w:len(self.enemy_positions[w]) for w in ['w', 'c', 's']}
        possibilities = sorted(possibilities.items(), key=lambda x:x[1])

        # 敵を攻撃する順番を指定。範囲がより絞れている敵から攻撃
        attack_order = [w[0] for w in possibilities]

        for enemy in attack_order:
            # 敵が死んでいる場合はその敵は無視
            if self.enemy_hp[enemy]==0:
                continue

            # 敵候補地が攻撃可能ならば、攻撃する
            if self.is_in_range(enemy):
                return self.attack_in_field(self.enemy_positions[enemy])
        # 敵候補地が攻撃できない場合適当な場所を攻撃する.
        return self.attack_in_field(self.field)

# 仕様に従ってサーバとソケット通信を行う．
def main(host, port, seed=0):
    assert isinstance(host, str) and isinstance(port, int)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((host, port))
        with sock.makefile(mode='rw', buffering=1) as sockfile:
            get_msg = sockfile.readline()
            print(get_msg)
            player = PlayerByHand()
            sockfile.write(player.initial_condition()+'\n')

            while True:
                info = sockfile.readline().rstrip()
                print(info)
                if info == "your turn":
                    sockfile.write(player.action()+'\n')
                    get_msg = sockfile.readline()
                    player.update(get_msg)
                elif info == "waiting":
                    get_msg = sockfile.readline()
                    player.update(get_msg)
                elif info == "you win":
                    break
                elif info == "you lose":
                    break
                elif info == "even":
                    break
                else:
                    raise RuntimeError("unknown information")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description="Sample Player for Submaline Game")
    parser.add_argument(
        "host",
        metavar="H",
        type=str,
        help="Hostname of the server. E.g., localhost",
    )
    parser.add_argument(
        "port",
        metavar="P",
        type=int,
        help="Port of the server. E.g., 2000",
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="Random seed of the player",
        required=False,
        default=0,
    )
    args = parser.parse_args()

    main(args.host, args.port, seed=args.seed)
