#!/usr/bin/env python3
import sys
import argparse

debug = False

sf_location = '/usr/local/Cellar/stockfish/13/bin/stockfish'

# limits are set with argparse now
depth_limit = None
time_limit = None
default_depth = 10

if debug:
    print('Version: {}'.format(sys.version))

import chess
import chess.pgn
import chess.engine
import re
import atexit

# RE setup
re_score_black = re.compile('PovScore\(Cp\(([\+|\-]?\d+)\), BLACK\)')
re_score_white = re.compile('PovScore\(Cp\(([\+|\-]?\d+)\), WHITE\)')
re_mate_white = re.compile('PovScore\(Mate\(([\+|\-]?\d+)\), WHITE\)')
re_mate_black = re.compile('PovScore\(Mate\(([\+|\-]?\d+)\), BLACK\)')

@atexit.register
def goodbye():
    try:
        engine.close()
    except:
        pass
    print('SUCCESS. Exit')

def proc_cp(input_dict):
    """ Calculate cp FROM current move to end...
    """

    w = list(input_dict['white'])
    b = list(input_dict['black'])

    print()
    print('> Calculating statistics for centipawn loss per move to the end...')
    print('> ie. first index indicates centipawn loss avg from that move to the end, etc...')
    print('> White moves: {}'.format(len(w)))
    print('> Black moves: {}'.format(len(b)))

    w_ret = []
    b_ret = []

    w_msg = None
    b_msg = None

    print()
    w_moves = len(w)
    b_moves = len(b)

    # Calculate for White
    #for x in range(0, w_moves):
    cur = 0 
    for x in range(cur, w_moves):
        cur_moves = w_moves - x 
        tot = 0 
        for i in range(cur, w_moves):
            tot += w[i]
    
        avg = round(tot / cur_moves, 1)
        cur += 1
        if avg == 0:
            if not w_msg:
                w_msg = 'White had no centipawn loss from move [{}] to move [{}]'.format(cur, w_moves)

        w_ret.append(avg)

    # Calculate for Black
    cur = 0 
    for x in range(cur, b_moves):
        cur_moves = b_moves - x 
        tot = 0 
        for i in range(cur, b_moves):
            if b[i] < 0:
                continue
            tot += b[i]

        avg = round(tot / cur_moves, 1)
        cur += 1

        b_ret.append(avg)

        if avg == 0:
            if not b_msg:
                b_msg = 'Black had no centipawn loss from move [{}] to move [{}]'.format(cur, b_moves)

    print('White:')
    print(w_ret)
    if w_msg:
        print('***')
        print(w_msg)
        print('***')
    print()
    print('Black:')
    print(b_ret)
    if b_msg:
        print('***')
        print(b_msg)
        print('***')
    print()


def get_score(score):
    score = str(score)
    m = re_score_white.match(score)
    if m:
        ret = m.group(1)
        ret = int(ret)
        return ret
    m = re_score_black.match(score)
    if m:
        ret = m.group(1)
        ret = int(ret) * -1
        return ret

    # When evaluating a position that evaluates to MATE IN X:
    # we are faced with some possibilities such as:
    m = re_mate_white.match(score)
    if m:
        # If POSITIVE number: white has mate in X - so return a positive eval
        # If NEGATIVE number: black has mate in X - so return a negative eval
        mate_in = int(m.group(1))
        if mate_in > 0:
            deduction = mate_in * 1000
            ret = 32765 - deduction
            return ret
        else:
            deduction = mate_in * -1000
            ret = 32765 - deduction
            ret = ret * -1
            return ret

    m = re_mate_black.match(score)
    if m:
        # If POSITIVE number: black has mate in X - so return a negative eval
        # If NEGATIVE number: white has mate in X - so return a positive eval
        mate_in = int(m.group(1))
        if mate_in > 0:
            deduction = mate_in * -1000
            ret = 32765 - deduction
            ret = ret * -1
            return ret
        else:
            deduction = mate_in * 1000
            ret = 32765 - deduction
            return ret

    print('ERROR: Cannot parse number from score: "{}"'.format(score))
    return None


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="blah description")
    parser.add_argument('pgnfile', help='The pgn file to eval')
    parser.add_argument('-d', '--depth', type=int, help='Set engine depth')
    parser.add_argument('-t', '--time', type=float, help='Set time depth')
    parser.add_argument('-c', '--centipawn', action='store_true', help='Include detailed centipawn calculations...')
    args = parser.parse_args()

    game_pgn = args.pgnfile

    if args.depth and args.time:
        print('You can only specify ONE - --depth or --time.')
        sys.exit(0)

    if args.depth:
        depth_limit = args.depth
        print('Parsing [{}] at depth limit of [{}]'.format(game_pgn, depth_limit))

    if args.time:
        time_limit = args.time
        print('Parsing [{}] at time limit of [{}]'.format(game_pgn, time_limit))

    if not args.depth and not args.time:
        depth_limit = default_depth
        print('INFO: Defaulting to depth limit of {}'.format(depth_limit))

    pgn = open(game_pgn)

    first_game = chess.pgn.read_game(pgn)
    engine = chess.engine.SimpleEngine.popen_uci(sf_location)

    board = first_game.board()

    mover = 'white'
    c_score = 0
    num_score = 0

    # Used to store centipawn calculations for each player
    cp_res = {}
    cp_res['white'] = []
    cp_res['black'] = []

    # Iterate through all moves and play them on a board.
    move_num = 1
    for move in first_game.mainline_moves():
        c_score = num_score

        if mover == 'white':
            prefix = ''
        else:
            prefix = '...'
        
        san = board.san(move)
        san = '{}{}'.format(prefix, san)

        board.push(move)
        if time_limit:
            info = engine.analyse(board, chess.engine.Limit(time=time_limit))
        if depth_limit:
            info = engine.analyse(board, chess.engine.Limit(depth=depth_limit))

        score = str(info['score'])
        num_score = get_score(score)
        

        try:
            move_diff = c_score - num_score
            
            # if move diff is a mate sequence (divisible by 1,000)
            # we will zero it out
            if move_diff % 1000 == 0:
                move_diff = 0

            # Cap at +- 1k
            if move_diff < -1000:
                move_diff = -1000
            elif move_diff > 1000:
                move_diff = 1000
            # Since we are calculating the move in CENTIPAWN LOSS
            # A negative number indicates a POSITIVE value so...
            if mover == 'black':
                move_diff = move_diff * -1

            # And finally, a result can't actually be better
            # As a negative difference would be an artifact of imperfect engine calculation
            if move_diff < 0:
                move_diff = 0
            cp_res[mover].append(move_diff)
        except:
            pass
        print('{:<3} {:<9} eval: {:<5}   {} loss: {}'.format(move_num, san, num_score, mover, move_diff))

        if mover == 'white':
            mover = 'black'
        else:
            mover = 'white'
            move_num += 1

    # Calculate centipawn loss avg...
    # TODO divide by zero if w_items or b_items = 0
    w_items = len(cp_res['white'])
    w_tot = 0
    for item in cp_res['white']:
        w_tot += item
    w_cp_avg = round(w_tot / w_items, 1)
    b_items = len(cp_res['black'])
    b_tot = 0
    for item in cp_res['black']:
        b_tot += item
    b_cp_avg = round(b_tot / b_items, 1)

    print('White avg cp loss: [{}]'.format(w_cp_avg))
    print('Black avg cp loss: [{}]'.format(b_cp_avg))

    engine.quit()

    if args.centipawn:
        proc_cp(cp_res)
