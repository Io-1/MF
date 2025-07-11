// static/game.js
$(function() {
    // how many slots on each side?
    const totalSlots = $('.left-slot').length;

  // pick a random trigger between 1 and totalSlots
  function getRandomInt(min, max) {
    return Math.floor(Math.random() * (max - min + 1)) + min;
  }
  
    // keep track of which slot indices have been emptied by matches
    let emptyLeft  = [];
    let emptyRight = [];
    let selection  = null;


  // how many matches before we refill everything?
  let refillThreshold = getRandomInt(1, totalSlots);
  console.log('🎲 will refill after', refillThreshold, 'matches');
  
    // Fisher–Yates shuffle
    function shuffle(arr) {
      for (let i = arr.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [arr[i], arr[j]] = [arr[j], arr[i]];
      }
      return arr;
    }
  
    // place a card DIV into the nth slot of the given side
    function placeCard(side, slotIdx, word, pairId) {
      // pick the correct .slot container
      const $slots = side === 'left'
        ? $('#left-cards .slot')
        : $('#right-cards .slot');
      const $slot = $slots.eq(slotIdx);
  
      console.log(`🃏 Placing [${word}] in ${side}-slot #${slotIdx}`, $slot);
      $slot.empty();
  
      // build & fade in the card
      const $card = $('<div>')
        .addClass(`card ${side}-card`)
        .attr('data-id', pairId)
        .attr('data-slot-index', slotIdx)
        .text(word)
        .hide();
      $slot.append($card);
      $card.fadeIn(200);
    }
  
    // get an array of all words currently on-screen
    function getCurrentWords() {
      return $('.card').map((_, el) => $(el).text()).get();
    }
  
    // wrapper for POST /new_pairs
    function fetchPairs(n, excludeWords, cb) {
      console.log(`🔄 Fetching ${n} pairs, excluding [${excludeWords.join(', ')}]`);
      $.ajax({
        url: '/new_pairs',
        method: 'POST',
        contentType: 'application/json',
        dataType: 'json',
        data: JSON.stringify({ n: n, exclude: excludeWords }),
        success: function(res) {
          console.log('🎁 Received pairs:', res.pairs);
          cb(res.pairs);
        },
        error: function(xhr, status, err) {
          console.error('❌ fetchPairs error:', status, err);
        }
      });
    }
  
    // initial fill of all slots
    function assignInitial() {
      fetchPairs(totalSlots, [], function(pairs) {
        const leftOrder  = shuffle([...Array(totalSlots).keys()]);
        const rightOrder = shuffle([...Array(totalSlots).keys()]);
  
        pairs.forEach((p, i) => {
          placeCard('left',  leftOrder[i],  p.left,  p.id);
          placeCard('right', rightOrder[i], p.right, p.id);
        });
      });
    }
  
    // refill exactly the emptied slots once two matches have been made
    function refillSlots() {
    // fill every slot we emptied
      const n = emptyLeft.length;
      const exclude = getCurrentWords();
      console.log('🔧 About to refill. emptyLeft:', emptyLeft, 'emptyRight:', emptyRight);
  
      fetchPairs(n, exclude, function(pairs) {
        // use the full list of emptied slots
        const slotsL = shuffle(emptyLeft);
        const slotsR = shuffle(emptyRight);
  
        pairs.forEach((p, i) => {
          placeCard('left',  slotsL[i], p.left,  p.id);
          placeCard('right', slotsR[i], p.right, p.id);
        });
  
        // clear the arrays for the next cycle
        emptyLeft  = [];
        emptyRight = [];
                // pick a brand‐new random threshold for the next refill
        refillThreshold = getRandomInt(2, totalSlots);
        console.log('🔄 next refill after', refillThreshold, 'matches');
      });
    }

  
    // click → select → match logic
// NEW: bidirectional click → select → match logic
$(document).on('pointerdown', '.card', function(e) {
  e.preventDefault();
  const $this   = $(this);
  const pairId  = $this.data('id');
  const side    = $this.hasClass('left-card') ? 'left' : 'right';
  const slotIdx = $this.data('slot-index');

  // 1) if nothing selected yet, pick this card
  if (!selection) {
    selection = { pairId, side, slotIdx, $el: $this.addClass('selected') };
    return;
  }

  // 2) clicked the same side again → switch selection
  if (selection.side === side) {
    selection.$el.removeClass('selected');
    selection = { pairId, side, slotIdx, $el: $this.addClass('selected') };
    return;
  }

  // 3) clicked the opposite side → attempt match
  if (selection.pairId === pairId) {
    // correct!
    selection.$el.fadeOut(200, () => selection.$el.remove());
    $this.fadeOut(200, () => $this.remove());

    // record freed slots
    if (selection.side === 'left') {
      emptyLeft.push(selection.slotIdx);
      emptyRight.push(slotIdx);
    } else {
      emptyLeft.push(slotIdx);
      emptyRight.push(selection.slotIdx);
    }

    // when 2 slots freed on each side, refill
    if (emptyLeft.length >= refillThreshold &&
      emptyRight.length >= refillThreshold) {
      refillSlots();
    }
  } else {
    // wrong match → just deselect the first
    selection.$el.removeClass('selected');
  }

  // static/game.js (inside your match logic)
  if (selection.pairId === pairId) {
    // mark both cards as matched
    selection.$el.addClass('matched');
    $this.addClass('matched');

    // and remove references immediately
    selection.$el.remove();
    $this.remove();

  // record freed slots…
}


  // reset selection for next round
  selection = null;
});

  
    // kick off
    assignInitial();
  });
  