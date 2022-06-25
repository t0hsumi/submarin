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

        # フィールドを2x2の配列として持っている．
        self.field = [[i, j] for i in range(Player.FIELD_SIZE)
                      for j in range(Player.FIELD_SIZE)]

        # 初期配置は広い範囲を攻撃できる場所に変更する。
        positions = {'w': [1,1], 'c': [3,2], 's': [1,3]}
        self.enemy_positions = {'w':[[i, j] for i in range(Player.FIELD_SIZE)
                                     for j in range(Player.FIELD_SIZE)],
                                'c':[[i, j] for i in range(Player.FIELD_SIZE)
                                     for j in range(Player.FIELD_SIZE)],
                                's':[[i, j] for i in range(Player.FIELD_SIZE)
                                     for j in range(Player.FIELD_SIZE)]}
        self.enemy_hp = {'w': 3, 'c': 2, 's': 1}
        self.have_attacked = False
        super().__init__(positions)

    # 攻撃してnearとなった場合の敵位置の更新
    def attack_near_update(self, near_target, attack_point):
        # nearに引っかかった場合多くとも8通りに絞られる
        possible_point = [[attack_point[0]+i, attack_point[1]+j]
                for i in range(-1, 2) for j in range(-1, 2) if not (i==0 and j==0)]
        for enemy in near_target:
            update_position = []
            for point in possible_point:
                if point in self.enemy_positions[enemy]:
                    update_position.append(point)
            self.enemy_positions[enemy] = update_position

    # # 敵からの攻撃による敵位置の更新
    # def enemy_attack_update(self, attack_point):
    #     possible_point = [[attack_point[0]+i, attack_point[1]+j]
    #             for i in range(-1, 2) for j in range(-1, 2) if not (i==0 and j==0)]
    #     for enemy in ['w', 'c', 's']:
    #         update_position = []
    #         for point in possible_point:
    #             if point in self.enemy_positions[enemy]:
    #                 update_position.append(point)
    #         self.enemy_positions[enemy] = update_position

    def enemy_movement_update(self, move_enemy, direction):
        update_position = []
        for point in self.enemy_positions[move_enemy]:
            move_to = [pos + direc for (pos, direc) in zip(point, direction)]
            if move_to[0] < super().FIELD_SIZE and move_to[1] < super().FIELD_SIZE \
                    and move_to[0] >= 0 and move_to[1] >= 0:
                update_position.append(move_to)
        self.enemy_positions[move_enemy] = update_position

    def update(self, json_):
        cond = json.loads(json_)

        # 自分の攻撃のフィードバック
        if self.have_attacked:
            attack_point = cond['result']['attacked']['position']
            if 'hit' in cond['result']['attacked']:
                is_attacked_enemy = cond['result']['attacked']['hit']
                self.enemy_positions[is_attacked_enemy] = [attack_point]
                self.enemy_hp[is_attacked_enemy] -= 1
            if 'near' in cond['result']['attacked']:
                self.attack_near_update(cond['result']['attacked']['near'], attack_point)
            self.have_attacked = False
        # 敵の行動のフィードバック
        elif 'result' in cond:
            if 'attacked' in cond['result']:
                # self.enemy_attack_update(cond['result']['attacked']['position'])
                print("I was attacked")
            if 'moved' in cond['result']:
                self.enemy_movement_update(cond['result']['moved']['ship'],
                                           cond['result']['moved']['distance'])
        print(cond)
        super().update(json_)

    #
    # 移動か攻撃かランダムに決める．
    # どれがどこへ移動するか，あるいはどこに攻撃するかもランダム．
    #
    def action(self):
        act = random.choice(["move", "attack"])

        if act == "move":
            ship = random.choice(list(self.ships.values()))
            to = random.choice(self.field)
            while not ship.can_reach(to) or not self.overlap(to) is None:
                to = random.choice(self.field)

            return json.dumps(self.move(ship.type, to))
        elif act == "attack":
            to = random.choice(self.field)
            self.have_attacked = True
            while not self.can_attack(to):
                to = random.choice(self.field)

            return json.dumps(self.attack(to))


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
