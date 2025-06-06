require('dotenv').config();
const sgMail = require('@sendgrid/mail');
sgMail.setApiKey(process.env.SENDGRID_API_KEY);

const msg = {
  to: 'your@personal.email', // Use your real email for testing
  from: 'noreply@bititecsystems.com', // Must be verified in SendGrid
  subject: 'SendGrid Test',
  text: 'If you can read this, SendGrid is working!',
};

sgMail.send(msg)
  .then(() => logger.debug('Email sent'))
  .catch(error => logger.error('Error:', error));