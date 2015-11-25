from bitcoin.main import *
from bitcoin.transaction import *
from bitcoin.bci import *
from bitcoin.deterministic import *
from bitcoin.blocks import *


# Takes privkey, address, value (satoshis), fee (satoshis)
def send(frm, to, value, fee=10000, **kwargs):
    return sendmultitx(frm, to + ":" + str(value), fee, **kwargs)


# Takes privkey, "address1:value1, address2:value2" (satoshis), fee (satoshis)
def sendmultitx(frm, *args, **kwargs):   # def sendmultitx(frm, tovalues, fee=10000, **kwargs)
    tv, fee = args[:-1], int(args[-1])
    outs = []
    outvalue = 0
    for a in tv:
        outs.append(a)
        outvalue += int(a.split(":")[1])

    u = unspent(privtoaddr(frm), **kwargs)
    u2 = select(u, int(outvalue)+int(fee))
    argz = u2 + outs + [privtoaddr(frm), fee]
    tx = mksend(*argz)
    tx2 = signall(tx, frm)
    return pushtx(tx2, **kwargs)


# Takes address, address, value (satoshis), fee(satoshis)
def preparetx(frm, to, value, fee=10000, **kwargs):
    """Composite from fromAddr, toAddr, value & fee"""
    tovalues = to + ":" + str(value)
    return preparemultitx(frm, tovalues, fee, **kwargs)


# Takes address, address:value, address:value ... (satoshis), fee(satoshis)
def preparemultitx(frm, *args, **kwargs):
    tv, fee = args[:-1], int(args[-1])
    outs = []
    outvalue = 0
    for a in tv:
        outs.append(a)
        outvalue += int(a.split(":")[1])

    u = unspent(frm, **kwargs)
    u2 = select(u, int(outvalue)+int(fee))
    argz = u2 + outs + [frm, fee]
    return mksend(*argz)


# BIP32 hierarchical deterministic multisig script
def bip32_hdm_script(*args):
    if len(args) == 3:
        keys, req, path = args
    else:
        i, keys, path = 0, [], []
        while len(args[i]) > 40:
            keys.append(args[i])
            i += 1
        req = int(args[i])
        path = map(int, args[i+1:])
    pubs = sorted(map(lambda x: bip32_descend(x, path), keys))
    return mk_multisig_script(pubs, req)


# BIP32 hierarchical deterministic multisig address
def bip32_hdm_addr(*args):
    return scriptaddr(bip32_hdm_script(*args))


# Setup a coinvault transaction
def setup_coinvault_tx(tx, script):
    txobj = deserialize(tx)
    N = deserialize_script(script)[-2]
    for inp in txobj["ins"]:
        inp["script"] = serialize_script([None] * (N+1) + [script])
    return serialize(txobj)


# Sign a coinvault transaction
def sign_coinvault_tx(tx, priv):
    pub = privtopub(priv)
    txobj = deserialize(tx)
    subscript = deserialize_script(txobj['ins'][0]['script'])
    oscript = deserialize_script(subscript[-1])
    k, pubs = oscript[0], oscript[1:-2]
    for j in range(len(txobj['ins'])):
        scr = deserialize_script(txobj['ins'][j]['script'])
        for i, p in enumerate(pubs):
            if p == pub:
                scr[i+1] = multisign(tx, j, subscript[-1], priv)
        if len(filter(lambda x: x, scr[1:-1])) >= k:
            scr = [None] + filter(lambda x: x, scr[1:-1])[:k] + [scr[-1]]
        txobj['ins'][j]['script'] = serialize_script(scr)
    return serialize(txobj)


# Inspects a transaction
def inspect(tx, **kwargs):
    d = deserialize(tx)
    isum = 0
    ins = {}
    for _in in d['ins']:
        h = _in['outpoint']['hash']
        i = _in['outpoint']['index']
        prevout = deserialize(fetchtx(h, **kwargs))['outs'][i]
        isum += prevout['value']
        a = script_to_address(prevout['script'])
        ins[a] = ins.get(a, 0) + prevout['value']
    outs = []
    osum = 0
    for _out in d['outs']:
        outs.append({'address': script_to_address(_out['script']),
                     'value': _out['value']})
        osum += _out['value']
    return {
        'fee': isum - osum,
        'outs': outs,
        'ins': ins
    }


def merkle_prove(txhash):
    blocknum = str(get_block_height(txhash))
    header = get_block_header_data(blocknum)
    hashes = get_txs_in_block(blocknum)
    i = hashes.index(txhash)
    return mk_merkle_proof(header, hashes, i)


def tx_size(txobj, unit="bytes"):
    """Get Tx size in bytes"""
    if isinstance(txobj, dict):
        return tx_size(serialize(txobj))
    assert unit in ("bytes", "kilobytes")
    if unit=='bytes':
        return len(txobj)
    elif unit=='kilobytes':
        return len(txobj) / 1024.0

def realtime_tx_fee(txobj, priority='medium'):
    """Get realtime Tx Fee (in Satoshis) for txobj"""
    assert priority in ('low', 'medium', 'high')
    if isinstance(txobj, dict):
        return realtime_tx_fee(serialize(txobj), priority)
    tx_size_kbytes = tx_size(txobj, unit='kilobytes')
    tx_fee_api = get_fee_estimate(priority)
    return int(tx_size_kbytes * tx_fee_api)


def estimate_tx_size(*args):
    """Estimate Tx size in bytes"""
    if not isinstance(txobj, dict):
        txobj = deserialize(txobj)
    ins   = txobj.get('ins',  [])
    outs  = txobj.get('outs', [])
    nins  = len(ins)  if 'ins' else 1
    nouts = len(outs) if 'outs' else 1
    return (nouts * 148) + (34 * nins) + 10
    
