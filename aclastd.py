#!/usr/bin/python

# This is a dummy peer that just illustrates the available information your peers 
# have available.  The setup script will copy it to create the versions you edit

import random
import logging

from messages import Upload, Request
from util import even_split
from peer import Peer

class AclaStd(Peer):
    def post_init(self):
        print("post_init(): %s here!" % self.id)
        ##################################################################################
        # Declare any variables here that you want to be able to access in future rounds #
        ##################################################################################

    
    def requests(self, peers, history):
        """
        peers: available info about the peers (who has what pieces)
        history: what's happened so far as far as this peer can see

        returns: a list of Request() objects

        This will be called after update_pieces() with the most recent state.
        """
        #Calculate the pieces you still need
        needed = lambda i: self.pieces[i] < self.conf.blocks_per_piece
        needed_pieces = list(filter(needed, list(range(len(self.pieces)))))
        np_set = set(needed_pieces)  # sets support fast intersection ops.


        logging.debug("%s here: still need pieces %s" % (
            self.id, needed_pieces))

        #This code shows you what you have access to in peers and history
        #You won't need it in your final solution, but may want to uncomment it
        #and see what it does to help you get started
        """
        logging.debug("%s still here. Here are some peers:" % self.id)
        for p in peers:
            logging.debug("id: %s, available pieces: %s" % (p.id, p.available_pieces))

        logging.debug("And look, I have my entire history available too:")
        logging.debug("look at the AgentHistory class in history.py for details")
        logging.debug(str(history))
        """

        # Symmetry breaking is good...
        random.shuffle(needed_pieces)

        # count frequencies of all pieces that the other peers have
        # this will be useful for implementing rarest first
        peers.sort(key=lambda p: p.id)

        # first we need to find the rarest piece
        frequencies = {}
        for peer in peers:
            # get set of available pieces for all peers
            rare_set = set(peer.available_pieces)
            for piece in rare_set:
                if piece not in frequencies.keys():
                    frequencies[piece] = [1, [peer.id]]
                else:
                    frequencies[piece][0] += 1
                    frequencies[piece][1].append(peer.id)
        
        requests = []   # We'll put all the things we want here

        # request all available pieces from all peers!
        # (up to self.max_requests from each)
        #############################################################################
        # This code now implements the rarest first algorithm                       #
        #############################################################################
        for peer in peers:
            # pieces this peer has available
            av_set = set(peer.available_pieces)

            # intersection between what user needs and what other peers have
            isect = av_set.intersection(np_set)

            if self.max_requests >= len(isect):
                # request message from peers added to requests
                for piece_id in isect:
                    start_block = self.pieces[piece_id]
                    r = Request(self.id, peer.id, piece_id, start_block)
                    requests.append(r)
            # rarest first                  
            else:
                isect_list = []
                # number of peers who have this piece and what piece
                for piece in isect:
                    isect_list.append((frequencies[piece][0],piece))

               # sort according to first index, which is # of peers who own it
                isect_list.sort()

                # the fewer peers have the piece, the rarer the piece is
                # find the # of peers who own the rarest piece 
                rarestCount = isect_list[0][0]

                # find equally rare pieces
                sameRareList = []
                for elem in isect_list:
                    if elem[0] == rarestCount:
                        sameRareList.append(elem[1])

                # order should be random   
                random.shuffle(sameRareList)

                # merge shuffled rarest list and the rest together
                secondList = []
                for p in isect_list[len(elem):]:
                    secondList.append(p[1])
                isectIDList = sameRareList + secondList

                # cut the list and get needed amount of peer IDs up to max_requests
                isectIDList = isectIDList[:self.max_requests]

                # write request message to the right peers 
                for piece_id in isectIDList:
                    start_block = self.pieces[piece_id]
                    r = Request(self.id, peer.id, piece_id, start_block)
                    requests.append(r)

        return requests

    def uploads(self, requests, peers, history):
        """
        requests -- a list of the requests for this peer for this round
        peers -- available info about all the peers
        history -- history for all previous rounds

        returns: list of Upload objects.

        In each round, this will be called after requests().
        """

        # get current round number to use as a replacement for "time"
        # here i am using 1 round to represent 10 seconds
        round = history.current_round()

        logging.debug("%s again.  It's round %d." % (self.id, round))
        # One could look at other stuff in the history too here.
        # For example, history.downloads[round-1] (if round != 0, of course)
        # has a list of Download objects for each Download to this peer in
        # the previous round.

        # if round >= 2 we have some history we can base our moves on
        if round >= 2:
            historyDict = {}
            
            # history of round - 1
            for download in history.downloads[round-1]:
                fromId = download.from_id
                if fromId not in historyDict.keys():
                    historyDict[fromId] = download.blocks
                else:
                    historyDict[fromId] += download.blocks
                    
            # history of round - 2
            for download in history.downloads[round-2]:
                fromId = download.from_id
                if fromId not in historyDict.keys():
                    historyDict[fromId] = download.blocks
                else:
                    historyDict[fromId] += download.blocks

        # there are no requests, so pass empty list
        if len(requests) == 0:
            logging.debug("No one wants my pieces!")
            chosen = []
            bws = []
        else:
            logging.debug("uploading to a random peer")
            chosen = []

            if round < 2:
                #randomly choose peers for unchoking slots
                requesters = []
                for request in requests:
                    if request.requester_id not in requesters:
                        requesters.append(request.requester_id)

                # append up to 4 random peers to lilst
                for i in range(0, 4):
                    if len(requests) != 0:
                        request = random.choice(requesters)
                        chosen.append(request)
                        requesters.remove(request)
               
            # round >= 2
            else:
                # select the top 3 to be in the unchoking slots
                requesters = []
                for request in requests:
                    if request.requester_id not in requesters:
                        requesters.append(request.requester_id)

                # append top 3 to rankList
                rankList = []
                for requester in requesters:
                    if requester not in historyDict.keys():
                        rankList.append((0, requester))
                    else:
                        rankList.append((historyDict[requester], requester))

                Slots = 3
                tempList = []

                # if length is <= 3, fill up those slots with top 3 peers
                if len(rankList) <= 3:
                    for elem in rankList:
                        tempList.append(elem[1])
                    Slots = 3 - len(rankList)
                else:
                    rankList.sort(reverse=True)
                    rankList = rankList[:3]
                    for elem in rankList:
                        tempList.append(elem[1])
                    Slots = 0

                for request in requests:
                    if request.requester_id in tempList:
                        requests.remove(request)
           
                # if top 3 slots aren't taken, randomly pick peers to unchoke
                for i in range(Slots):
                    if len(requests) != 0:
                        request = random.choice(requests)
                        tempList.append(request.requester_id)
                        requests.remove(request)

                # get upload history of last round
                prevUploadHist = history.uploads[round-1]
                for i in range(len(prevUploadHist)):
                    chosen.append(prevUploadHist[i].to_id)

                if round % 3 == 0:
                    # if the slots are full last round, copy all slots
                    if len(chosen) == 4:
                        for i in range(len(tempList)):
                            chosen[i] = tempList[i]
                    # if last round's optimistic unchoking is not chosen this round
                    else:
                        if chosen != [] and chosen[-1] not in tempList:
                            # copy optimistic unchoking from last round
                            last = chosen[-1]
                            chosen = []
                            for i in range(len(tempList)):
                                chosen.append(tempList[i])
                            chosen.append(last)
                        # if last round's slots are all empty
                        else:
                            chosen = []
                            for i in range(len(tempList)):
                                chosen.append(tempList[i])
                            
                            # add random peer to extra slot
                            for i in range(4 - len(tempList)):
                                if len(requests) != 0:
                                    request = random.choice(requests)
                                    chosen.append(request.requester_id)
                                    requests.remove(request)
                else:
                    chosen = tempList
                    if len(requests) > 0:
                        # optimistic unchoking
                        request = random.choice(requests)
                        chosen.append(request.requester_id)

            
            # Now that we have chosen who to unchoke,
            # the standard client evenly shares its bandwidth among them
            bws = even_split(self.up_bw, len(chosen))

        # create actual uploads out of the list of peer ids and bandwidths
        # You don't need to change this
        uploads = [Upload(self.id, peer_id, bw) for (peer_id, bw) in zip(chosen, bws)]
            
        return uploads