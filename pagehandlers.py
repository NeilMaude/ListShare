# This next part is handler code, which can probably be moved to a class file at some point
# There are also some security functions which should also be a in separate class file
import webapp2
import jinja2
import os
from datetime import datetime, timedelta

template_dir = os.path.join(os.path.dirname(__file__), 'templates')                 # Complains on first run that 'markupsafe' is not present
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir),
                               autoescape = True)

import parameters   # global parameter file
import users        # user account handling for this solution
import mailing      # email handling for this solution

class phPageHandler(webapp2.RequestHandler):
    # Generic page handler class - not called, overloaded by a named class for the page type
    # This page should always show a "work in progress page", if called directly
    def write(self, *a, **kw):
        self.response.out.write(*a, **kw)

    def render_str(self, template, **params):
        params['user'] = self.user
        t = jinja_env.get_template(template)
        return t.render(params)

    def render(self, template, **kw):
        self.write(self.render_str(template, **kw))

    #def render_json(self, d):
    #    json_txt = json.dumps(d)
    #    self.response.headers['Content-Type'] = 'application/json; charset=UTF-8'
    #    self.write(json_txt)

    def set_secure_cookie(self, name, val, remember):
        cookie_val = users.make_secure_val(val)
        if remember:
            delta_interval = timedelta(days = 5 * 365.25)                       # persist for 5 years
            s_expiry = (datetime.utcnow() + delta_interval).strftime("%d %B %Y %H:%M:%S") + ' GMT'
            self.response.headers.add_header(
                'Set-Cookie',
                '%s=%s; Path=/; Expires=%s' % (name, cookie_val, s_expiry))     # persist for 5 years
        else:
            self.response.headers.add_header(
                'Set-Cookie',
                '%s=%s; Path=/' % (name, cookie_val))

    def read_secure_cookie(self, name):
        cookie_val = self.request.cookies.get(name)
        return cookie_val and users.check_secure_val(cookie_val)

    def login(self, user, remember):
        self.set_secure_cookie('user_id', str(user.key().id()), remember)

    def logout(self):
        self.response.headers.add_header('Set-Cookie', 'user_id=; Path=/')

    def initialize(self, *a, **kw):
        webapp2.RequestHandler.initialize(self, *a, **kw)
        uid = self.read_secure_cookie('user_id')
        self.user = uid and users.User.by_id(int(uid))
        self.format = 'html'
        #if self.request.url.endswith('.json'):
        #    self.format = 'json'
        #else:
        #    self.format = 'html'


class phFront(phPageHandler):
    def get(self):
        if self.user:
            user_name = self.user.name
            self.render('construction.html', user_name = user_name)
            #s_ConstructionLogout = '<a href="/logout">' + user_name + '</a>'
        else:
            #user_name = '(Not logged in)'                                  # will eventually redirect to /welcome, once login is complete
            self.redirect('/welcome')
        

class phWelcome(phPageHandler):
    def get(self):
        if self.user:
            self.redirect("/")              # can't use the welcome page if logged in
        else:
            self.render('welcome.html')

# Welcome page needs to check for a logged-in user and redirect to home, if logged in
# Need also a nicer layout

class phFAQ(phPageHandler):
    def get(self):
        self.render('construction.html')

# Need a proper template, plus handling of login state in header nav bar

class phSignUp(phPageHandler):
    def get(self):
        if self.user:
            self.redirect('/')              # already logged in, can't create a new user here
        else:
            self.render('signup.html')

    def post(self):
         # have 'username', 'email', 'password1', 'password2', 'terms', 'remember-me' fields from the form
        have_error = False
        #self.username = self.request.get('username')
        self.username = self.request.get('email')           # use e-mail as the user name
        self.password = self.request.get('password1')
        self.verify = self.request.get('password2')
        self.email = self.request.get('email')
        self.terms = self.request.get('terms')
        self.remember = self.request.get('remember-me')

        params = dict(username = self.username,
                email_address = self.email,
                error_text = '')

        #if not users.valid_username(self.username):
        #    params['error_text'] = u"That's not a valid username."
        #    have_error = True
        if not users.valid_email(self.email):
            params['error_text'] = "That's not a valid email."
            have_error = True
        elif not users.valid_password(self.password):
            params['error_text'] = "That wasn't a valid password."
            have_error = True
        elif self.password != self.verify:
            params['error_text'] = "Your passwords didn't match."
            have_error = True
        elif not self.terms:
            params['error_text'] = "You must accept the terms and conditions in order to use this site."
            have_error = True

        if have_error:
            self.render('signup.html', **params)
        else:
            #make sure the user doesn't already exist
            u = users.User.by_name(self.username)
            if u:
                self.render('signup.html', error_text = 'A user with that e-mail address already exists.')
            else:
                u = users.User.register(self.username, self.password, self.email)
                u.put()
                if self.remember != '':
                    self.login(u, True)
                else:
                    self.login(u, False)
                mailing.welcome_signup(self.email)      # have now logged-in, send a welcome e-mail
                self.redirect('/')


class phSignIn(phPageHandler):
    def get(self):
        if self.user:
            self.redirect('/')                  # can't sign in again...
        else:
            self.render('signin.html')

    def post(self):
        username = self.request.get('email')
        password = self.request.get('password')
        self.remember = self.request.get('remember-me')

        u = users.User.login(username, password)
        if u:
            if self.remember != '':
                self.login(u, True)
            else:
                self.login(u, False)
            self.redirect('/')
        else:
            msg = 'Invalid login'
            self.render('signin.html', error_text = msg)


class phTutorial(phPageHandler):
    def get(self):
        self.render('construction.html')

class phFeedback(phPageHandler):
    def get(self):
        if self.user:
            self.render('construction.html')
        else:
            self.redirect('/welcome')           # if not logged in, can't provide feedback

class phLogout(phPageHandler):
    def get(self):
        self.logout()
        self.redirect('/welcome')               # should this go to the login screen instead?

class phReportEmail(phPageHandler):
    def get(self):
        self.render('construction.html')

class phRetrievePasswordSent(phPageHandler):
    def get(self):
        self.render('/retrieve_password_sent.html')

class phRetrievePassword(phPageHandler):
    def get(self):
        self.render('/retrieve_password.html')

    def post(self):
        user = self.request.get('email')

        # check if the user exists - if not, fail and redirect to this page again (with error text)
        u = users.User.by_name(user)
        if u:
            # found the user - OK to continue
            # create a random string
            # create a hash value of that string
            s, h = users.make_token()
            rp = users.Retrieve_Password.store_request(user, h)     # get a new data object
            rp.put()                                                # save it                
            # send the e-mail to the user, with the original random string
            mailing.send_password_reset(user, s)
            # redirect to the "reminder sent" page
            self.redirect('/retrieve_password_sent')
        else:
            # user doesn't exist
            self.render('retrieve_password.html', error_text = 'There is no user with that e-mail address.')

class phResetPassword(phPageHandler):
    def get(self):
        s = self.request.get('ID')                              # This will hold the random string
        # get the e-mail address from the database, checking that we have a match
        h = users.get_token_hash(s)
        rp = users.Retrieve_Password.by_hash(h)                 # Get back the retrieve password object
        if rp:
            rp_age = (datetime.utcnow() - rp.created).total_seconds()
            if rp_age <= parameters.RESET_PASSWORD_MAX_TIME_SECONDS:
                # OK to record the value in a temp cookie, it can't be forged to change any other user
                self.set_secure_cookie('reset_id', str(s), False)
                self.render('reset_password.html', user_name = rp.username)
            else:
                # delete the record
                rp.delete()
                self.redirect('/retrieve_password')                 # The timelimit has passed
        else:
            self.redirect('/retrieve_password')                 # no valid hash, send them to the retrieve screen

    def post(self):
        have_error = False
        s = self.read_secure_cookie('reset_id')                 # this should already be set
        s_password = self.request.get('password1')
        s_verify = self.request.get('password2')
        
        if s:
            h = users.get_token_hash(s)
            rp = users.Retrieve_Password.by_hash(h)
            if rp:
                rp_age = (datetime.utcnow() - rp.created).total_seconds()
                if rp_age <= parameters.RESET_PASSWORD_MAX_TIME_SECONDS:
                    # have a valid hash, within the time limit
                    # check for any errors, such as mis-matched passwords
                    if not users.valid_password(s_password):
                        s_error = "That wasn't a valid password."
                        have_error = True
                    elif s_password != s_verify:
                        s_error = "Your passwords didn't match."
                        have_error = True        
                    if have_error:
                        self.render('reset_password.html', user_name = rp.username, error_text = s_error)
                    else:
                        # have a valid user and a checked new password
                        # update the user password
                        u = users.User.change_password(rp.username, s_password)
                        u.put()
                        rp.delete()     # can't use this token again
                        #redirect to the login screen
                        #self.render('signin.html', error_text = 'Password changed')
                        self.redirect('/signin')
                else:
                    # delete the record and redirect the user - likely that the timelimit has passed
                    rp.delete()
                    self.redirect('/retrieve_password')
            else:
                self.redirect('/retrieve_password')
        else:
            self.redirect('/retrieve_password')                 # shouldn't ever be possible, but just in case...