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
  
  // Load schedules on page load
  loadSchedules();
});

// Schedule management functions
function loadSchedules() {
    fetch('/schedules')
        .then(response => response.json())
        .then(schedules => {
            const scheduleList = document.getElementById('schedule-list');
            scheduleList.innerHTML = '';
            
            if (schedules.length === 0) {
                scheduleList.innerHTML = '<p style="text-align: center; color: #666;">No schedules configured</p>';
                return;
            }
            
            schedules.forEach(schedule => {
                const scheduleItem = document.createElement('div');
                scheduleItem.className = 'schedule-item';
                scheduleItem.innerHTML = `
                    <div class="schedule-info">
                        <strong>${schedule.time}</strong> - Turn all lights <strong>${schedule.action}</strong>
                    </div>
                    <div class="schedule-actions">
                        <button class="btn-toggle ${schedule.enabled ? 'enabled' : 'disabled'}" 
                                onclick="toggleSchedule(${schedule.id})">
                            ${schedule.enabled ? 'Enabled' : 'Disabled'}
                        </button>
                        <button class="btn-delete" onclick="deleteSchedule(${schedule.id})">Delete</button>
                    </div>
                `;
                scheduleList.appendChild(scheduleItem);
            });
        })
        .catch(error => {
            console.error('Error loading schedules:', error);
            showFeedback('Error loading schedules', true);
        });
}

function addSchedule() {
    const time = document.getElementById('schedule-time').value;
    const action = document.getElementById('schedule-action').value;
    
    if (!time) {
        showFeedback('Please select a time', true);
        return;
    }
    
    fetch('/schedules', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ time, action })
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            showFeedback(data.error, true);
        } else {
            showFeedback('Schedule added successfully');
            document.getElementById('schedule-time').value = '';
            loadSchedules();
        }
    })
    .catch(error => {
        console.error('Error adding schedule:', error);
        showFeedback('Error adding schedule', true);
    });
}

function deleteSchedule(scheduleId) {
    if (!confirm('Are you sure you want to delete this schedule?')) {
        return;
    }
    
    fetch(`/schedules/${scheduleId}`, {
        method: 'DELETE'
    })
    .then(response => response.json())
    .then(data => {
        showFeedback('Schedule deleted successfully');
        loadSchedules();
    })
    .catch(error => {
        console.error('Error deleting schedule:', error);
        showFeedback('Error deleting schedule', true);
    });
}

function toggleSchedule(scheduleId) {
    fetch(`/schedules/${scheduleId}/toggle`, {
        method: 'PUT'
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            showFeedback(data.error, true);
        } else {
            showFeedback(`Schedule ${data.enabled ? 'enabled' : 'disabled'}`);
            loadSchedules();
        }
    })
    .catch(error => {
        console.error('Error toggling schedule:', error);
        showFeedback('Error toggling schedule', true);
    });
}

// Make showFeedback available globally
window.showFeedback = function(message, isError = false) {
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
};
