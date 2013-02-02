"""
Marker shifting map:

    The marker present in the models are:

    ReceiverTip    [ u'not notified', u'notified', u'unable to notify', u'notification ignore' ]
    File           [ u'not processed', u'ready', u'blocked', u'stored' ]
    InternalTip    [ u'new', u'first', u'second' ]
    Submission     [ u'incomplete', u'finalized' ]


"""

from globaleaks.transactors.base import MacroOperation

from globaleaks.models.node import Node
from globaleaks.models.receiver import Receiver
from globaleaks.models.externaltip import File, ReceiverTip, Comment
from globaleaks.models.internaltip import InternalTip
from globaleaks.models.submission import Submission
from globaleaks.models.options import PluginProfiles, ReceiverConfs
from globaleaks.plugins.manager import PluginManager
from globaleaks.config import config
import os

from storm.twisted.transact import transact

class AsyncOperations(MacroOperation):

    @transact
    def tip_notification(self):

        plugin_type = u'notification'
        store = self.getStore()

        receivertip_iface = ReceiverTip(store)
        receivercfg_iface = ReceiverConfs(store)
        profile_iface = PluginProfiles(store)

        not_notified_tips = yield receivertip_iface.get_tips_by_notification_mark(u'not notified')

        for single_tip in not_notified_tips:

        # from a single tip, we need to extract the receiver, and then, having
        # context + receiver, find out which configuration setting has active

            receivers_map = yield receivertip_iface.get_receivers_by_tip(single_tip['tip_gus'])

            receiver_info = receivers_map['actor']

            receiver_conf = yield receivercfg_iface.get_active_conf(receiver_info['receiver_gus'],
               single_tip['context_gus'], plugin_type)

            if receiver_conf is None:
               print "Receiver", receiver_info['receiver_gus'],\
               "has not an active notification settings in context", single_tip['context_gus'], "for", plugin_type
                # TODO separate key in answer
               continue

            # Ok, we had a valid an appropriate receiver configuration for the notification task
            related_profile = profile_iface.get_single(receiver_conf['profile_gus'])

            settings_dict = { 'admin_settings' : related_profile['admin_settings'],
                             'receiver_settings' : receiver_conf['receiver_settings']}

            plugin = PluginManager.instance_plugin(related_profile['plugin_name'])

            updated_tip = receivertip_iface.update_notification_date(single_tip['tip_gus'])
            return_code = plugin.do_notify(settings_dict, u'tip', updated_tip)

            if return_code:
               receivertip_iface.flip_mark(single_tip['tip_gus'], u'notified')
            else:
               receivertip_iface.flip_mark(single_tip['tip_gus'], u'unable to notify')

    @transact
    def comment_notification(self):

        plugin_type = u'notification'
        store = self.getStore()

        comment_iface = Comment(store)
        internaltip_iface = InternalTip(store)
        receivercfg_iface = ReceiverConfs(store)
        profile_iface = PluginProfiles(store)

        not_notified_comments = yield comment_iface.get_comment_by_mark(marker=u'not notified')

        for comment in not_notified_comments:

            receivers_list = yield internaltip_iface.get_receivers_by_itip(comment['internaltip_id'])

            # needed to obtain context!
            itip_info = yield internaltip_iface.get_single(comment['internaltip_id'])

            for receiver_info in receivers_list:

                receiver_conf = yield receivercfg_iface.get_active_conf(receiver_info['receiver_gus'],
                    itip_info['context_gus'], plugin_type)

                if receiver_conf is None:
                    # TODO applicative log, database tracking of queue
                    continue

                # Ok, we had a valid an appropriate receiver configuration for the notification task
                related_profile = yield profile_iface.get_single(receiver_conf['profile_gus'])

                settings_dict = { 'admin_settings' : related_profile['admin_settings'],
                                  'receiver_settings' : receiver_conf['receiver_settings']}

                plugin = PluginManager.instance_plugin(related_profile['plugin_name'])

                return_code = plugin.do_notify(settings_dict, u'comment', comment)

                if return_code:
                    print "Notification of comment successful for user", receiver_conf['receiver_gus']
                else:
                    print "Notification of comment failed for user", receiver_conf['receiver_gus']

            # remind: comment are not guarantee until Task manager is not developed
            yield comment_iface.flip_mark(comment['comment_id'], u'notified')

    @transact
    def fileprocess(self):

        plugin_type = u'fileprocess'

        store = self.getStore()

        file_iface = File(store)
        profile_iface = PluginProfiles(store)

        not_processed_file = file_iface.get_file_by_marker(file_iface._marker[0])

        for single_file in not_processed_file:

            profile_associated = profile_iface.get_profiles_by_contexts([ single_file['context_gus'] ] )

            for p_cfg in profile_associated:

                if p_cfg['plugin_type'] != plugin_type:
                    continue

                print "processing", single_file['file_name'], "using the profile", p_cfg['profile_gus'], "configured for", p_cfg['plugin_name']
                plugin = PluginManager.instance_plugin(p_cfg['plugin_name'])

                try:
                    tempfpath = os.path.join(config.advanced.submissions_dir, single_file['file_gus'])
                except AttributeError:
                    # XXX hi level danger Log - no directory present to perform file analysis
                    continue

                return_code = plugin.do_fileprocess(tempfpath, p_cfg['admin_settings'])

                # Todo Log/stats in both cases
                if return_code:
                    file_iface.flip_mark(single_file['file_gus'], file_iface._marker[1]) # ready
                else:
                    file_iface.flip_mark(single_file['file_gus'], file_iface._marker[2]) # blocked

    @transact
    def delivery(self):
        pass

    @transact
    def receiver_welcome(self):

        store = self.getStore()

        # receiver_iface = Receiver(store)
        # noobceivers = receiver_iface.get_receiver_by_marker(receiver_iface._marker[0) # 'not welcomed'
        # for noob in noobceivers:
        #    print "need to be welcomed", noob

    @transact
    def statistics(self):
        pass

    @transact
    def cleaning(self):
        pass

    @transact
    def check_update(self):
        pass
