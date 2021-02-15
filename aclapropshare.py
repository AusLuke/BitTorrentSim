#!/usr/bin/python

# This is a dummy peer that just illustrates the available information your peers 
# have available.  The setup script will copy it to create the versions you edit

import random
import logging

from messages import Upload, Request
from util import even_split
from peer import Peer

class AclaPropShare(Peer):
    def post_init(self):
        print("post_init(): %s here!" % self.id)
        ##################################################################################
        # Declare any variables here that you want to be able to access in future rounds #
        ##################################################################################

        #This commented out code is and example of a python dictionsary,
        #which is a convenient way to store a value indexed by a particular "key"
        #self.dummy_state = dict()
        #self.dummy_state["cake"] = "lie"
    
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
        logging.debug("%s still here. Here are some peers:" % self.id)
        for p in peers:
            logging.debug("id: %s, available pieces: %s" % (p.id, p.available_pieces))

        logging.debug("And look, I have my entire history available too:")
        logging.debug("look at the AgentHistory class in history.py for details")
        logging.debug(str(history))

        requests = []   # We'll put all the things we want here
        # Symmetry breaking is good...
        random.shuffle(needed_pieces)

        # count frequencies of all pieces that the other peers have
        # this will be useful for implementing rarest first
        ###########################################################
        # you'll need to write the code to compute these yourself #
        ###########################################################
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

        ##############################################################################
        # The code and suggestions here will get you started for the standard client #
        # You'll need to change things for the other clients                         #
        ##############################################################################

        round = history.current_round()
        logging.debug("%s again.  It's round %d." % (
            self.id, round))
        # One could look at other stuff in the history too here.
        # For example, history.downloads[round-1] (if round != 0, of course)
        # has a list of download objects for each download to this peer in
        # the previous round.

        uploads = []

        if round > 0:
            # get download history
            prevDownHistory = history.downloads[round-1]
            historyDict = {}
            
            # history of [round - 1]
            for download in history.downloads[round-1]:
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
            logging.debug("Still here: uploading to a random peer")

            # get requester List
            requesters = []
            for request in requests:
                if request.requester_id not in requesters:
                    requesters.append(request.requester_id)

            # dictionary for who to upload to
            unchokingDict = {}
            for requester in requesters:
                if requester in historyDict.keys():
                    unchokingDict[requester] = historyDict[requester]

            # get total blocks first
            totalBlocks = 0
            for peer in unchokingDict.keys():
                totalBlocks += unchokingDict[peer]

            # reserve a 10% share of bandwidth for optimistic unchoking
            optBwidthRate = 0.1
            # calculate % for each peer in unchoking dictionary
            for peer in unchokingDict.keys():
                percentage = (unchokingDict[peer] / totalBlocks) * (1 - optBwidthRate)
                unchokingDict[peer] = percentage

            # leave candidate for optimistic unchoking in requests
            for request in requests:
                    if request.requester_id in unchokingDict.keys():
                        requests.remove(request)

            # get upload list with: (id, peer, int(bandwidth * upload %))
            uploads = []
            for peer in unchokingDict.keys():
                percentage = unchokingDict[peer]
                uploads.append(Upload(self.id, peer, int(self.up_bw * percentage)))

            # add optimistic unchoke
            if len(requests) > 0:
                optimisticUnchoke = random.choice(requests)
                requestID = optimisticUnchoke.requester_id
                bandwidthForOptim = self.up_bw * optBwidthRate
                uploads.append(Upload(self.id, requestID, int(bandwidthForOptim)))
            
        return uploads