# -*- coding: utf-8 -*-
"""
Ingilizcenin en sik kullanilan ~700 kelimesi (fonksiyon kelimeleri +
gunluk temel kelime hazinesi). YDS sorularinda sinyal degil gurultu
olusturduklari icin kelime frekans analizinde elenirler.

Bu liste tam/resmi bir "top 1000" kaynagindan degil, derlenmis genel
bir listedir; amac kesin bilimsel siralama degil, en bariz gurultuyu
elemektir.
"""

COMMON_WORDS = set("""
the be to of and a in that have i it for not on with he as you do at
this but his by from they we say her she or an will my one all would
there their what so up out if about who get which go me when make can
like time no just him know take people into year your good some could
them see other than then now look only come its over think also back
after use two how our work first well way even new want because any
these give day most us is are was were been being am has had does did
doing having shall should may might must can't don't won't wouldn't
couldn't shouldn't isn't aren't wasn't weren't hasn't haven't hadn't
i'm you're he's she's it's we're they're i've you've we've they've
i'll you'll he'll she'll we'll they'll i'd you'd he'd she'd we'd they'd
here there when where why how all any both each few more most other
some such no nor not only own same so than too very s t just don now
myself yourself himself herself itself ourselves yourselves themselves
what which who whom this that these those am is are was were be been
being have has had having do does did doing a an the and but if or
because as until while of at by for with about against between into
through during before after above below to from up down in out on off
over under again further then once here there all any both each few
more most other some such no nor not only own same so than too very
can will just should now people man men woman women child children
year years day days time times life world hand hands part parts place
places case cases week weeks company companies system systems program
programs question questions government number numbers night nights
point points home homes water rooms mother area money story fact
month lot right study book eyes job word words business issue side
kind head house service friend father power hour game line end member
law car city community name president team minute idea body
information back parent face others level office door health nation
across country school student group country war problem money story
example students found state control public today market development
economic economy political social national international policy
process research education field science plan quality result
significant according general common similar particular various
several major several available important different possible
necessary certain individual special local recent early late high
low large small big little long short great good bad new old young
next last own same different same able likely unlikely certain sure
whole entire complete full empty easy hard difficult simple similar
increase decrease reduce grow rise fall change develop provide
include require allow suggest indicate show demonstrate reveal
consider believe understand explain describe discuss argue claim
report note mention state add continue begin start end finish stop
keep remain become seem appear tend result lead cause affect impact
influence effect example instance case study research evidence data
information knowledge fact idea theory concept model approach method
process system structure function role factor element aspect feature
characteristic property quality nature type kind sort form pattern
trend rate level degree extent range amount number percentage
proportion majority minority portion part whole total sum average
mean median standard normal typical common usual regular frequent
rare unusual unique special particular specific general overall
somewhat rather quite fairly relatively extremely highly greatly
significantly considerably substantially dramatically gradually
suddenly immediately eventually finally initially originally
previously subsequently currently recently lately nowadays today
tomorrow yesterday soon later earlier before after during while
whenever wherever whatever whoever however whichever although though
unless since because so that in order to as well as such as rather
than instead of because of due to according to in spite of despite
regardless nevertheless nonetheless furthermore moreover additionally
similarly likewise conversely however whereas while although though
unless until since as though as if provided provided that assuming
given that so that in that except that other than rather than
""".split())
