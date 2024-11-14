document.addEventListener('DOMContentLoaded', function() {

  // Function to show feedback messages
  function showFeedback(message, isError = false) {
      const feedback = document.getElementById('feedback');
      feedback.textContent = message;
      if (isError) {
          feedback.classList.add('error');
      } else {
          feedback.classList.remove('error');
      }
      feedback.style.display = 'block';
      setTimeout(() => {
          feedback.style.display = 'none';
      }, 3000);
  }

  // Helper function to handle fetch responses
  function handleResponse(response) {
      // Check if the response is JSON; if not, throw an error
      if (!response.ok) {
          return response.text().then(text => { throw new Error(text); });
      }
      return response.json();
  }

  // Event listeners for individual light buttons
  const buttons = document.querySelectorAll('.btn');
  buttons.forEach(button => {
      button.addEventListener('click', function() {
          const ip = this.getAttribute('data-ip');
          const action = this.getAttribute('data-action');
          let endpoint = '';
          let command = '';

          if (action === 'on') {
              endpoint = `/on/${encodeURIComponent(ip)}`;
              command = 'ON';
          } else if (action === 'off') {
              endpoint = `/off/${encodeURIComponent(ip)}`;
              command = 'OFF';
          }

          fetch(endpoint, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({})
          })
          .then(handleResponse)
          .then(data => {
              if (data.success) {
                  showFeedback(`Successfully turned ${command} ${ip}.`);
              } else {
                  showFeedback(`Failed to turn ${command} ${ip}: ${data.error}`, true);
              }
          })
          .catch((error) => {
              console.error(`Error with command ${command} for ${ip}:`, error);
              //showFeedback(`Error: ${error.message}`, true);
          });
      });
  });

  // Event listeners for all lights buttons
  const allOnButton = document.getElementById('all-on');
  const allOffButton = document.getElementById('all-off');

  allOnButton.addEventListener('click', function() {
      fetch('/on_all', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({})
      })
      .then(handleResponse)
      .then(data => {
          if (data.success) {
              showFeedback('Successfully turned ALL lights ON.');
          } else {
              showFeedback('Failed to turn ALL lights ON: ' + data.error, true);
          }
      })
      .catch((error) => {
          console.error("Error turning all lights ON:", error);
          //showFeedback(`Error: ${error.message}`, true);
      });
  });

  allOffButton.addEventListener('click', function() {
      fetch('/off_all', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({})
      })
      .then(handleResponse)
      .then(data => {
          if (data.success) {
              showFeedback('Successfully turned ALL lights OFF.');
          } else {
              showFeedback('Failed to turn ALL lights OFF: ' + data.error, true);
          }
      })
      .catch((error) => {
          console.error("Error turning all lights OFF:", error);
          //showFeedback(`Error: ${error.message}`, true);
      });
  });
});
